"""Build a compact, auditable Markdown/SVG presentation from an ES MILP run."""
from __future__ import annotations

import argparse
import html
import json
import math
import mmap
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

MADRID = ZoneInfo('Europe/Madrid')
MARKETS = ('DA', 'ID', 'cap_up', 'cap_down', 'act_up', 'act_down')
LABELS = {
    'DA': 'DA', 'ID': 'ID', 'cap_up': 'aFRR capacity up',
    'cap_down': 'aFRR capacity down', 'act_up': 'aFRR activation up',
    'act_down': 'aFRR activation down',
}
LABELS_ZH = {
    'DA': 'DA电能', 'ID': 'ID电能', 'cap_up': 'aFRR容量上调',
    'cap_down': 'aFRR容量下调', 'act_up': 'aFRR激活上调',
    'act_down': 'aFRR激活下调',
}
COLORS = {
    'DA': '#4472C4', 'ID': '#ED7D31', 'cap_up': '#70AD47',
    'cap_down': '#A5A5A5', 'act_up': '#FFC000', 'act_down': '#8064A2',
}


def _read_rows(path: Path) -> list[dict]:
    """Read only the top-level rows array from a large result JSON."""
    with path.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        marker = b'"rows": ['
        start = data.find(marker)
        months = data.find(b'"months":', start)
        end = data.rfind(b']', start, months)
        if min(start, months, end) < 0:
            raise ValueError(f'Cannot locate result rows in {path}')
        # Keep the opening '[' in the extracted array.
        return json.loads(data[start + len(b'"rows": '):end + 1].decode('utf-8'))


def _top_level_scalars(path: Path, wanted: set[str]) -> dict:
    """Extract selected scalar config values without loading the huge solver input."""
    patterns = {
        key: re.compile(rb'^  "' + re.escape(key.encode()) + rb'"\s*:\s*([^,\r\n]+)', re.M)
        for key in wanted
    }
    result = {}
    with path.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        for key, pattern in patterns.items():
            match = pattern.search(data)
            if not match:
                raise ValueError(f'Missing top-level input field {key!r}')
            result[key] = json.loads(match.group(1).strip().decode('utf-8'))
    return result


def _iter_json_array(path: Path):
    """Iterate an array of JSON objects from disk with bounded memory."""
    with path.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        i = data.find(b'[') + 1
        if i == 0:
            raise ValueError(f'Expected a JSON array in {path}')
        size = len(data)
        while i < size:
            while i < size and data[i] in b' \r\n\t,':
                i += 1
            if i >= size or data[i] == ord(']'):
                return
            if data[i] != ord('{'):
                raise ValueError(f'Expected object at byte {i} in {path}')
            start = i
            depth = 0
            in_string = False
            escaped = False
            while i < size:
                byte = data[i]
                if in_string:
                    if escaped:
                        escaped = False
                    elif byte == ord('\\'):
                        escaped = True
                    elif byte == ord('"'):
                        in_string = False
                elif byte == ord('"'):
                    in_string = True
                elif byte == ord('{'):
                    depth += 1
                elif byte == ord('}'):
                    depth -= 1
                    if depth == 0:
                        i += 1
                        yield json.loads(data[start:i].decode('utf-8'))
                        break
                i += 1
            else:
                raise ValueError(f'Unclosed JSON object in {path}')


def _madrid_time(row: dict) -> datetime:
    value = datetime.fromisoformat(row['time'].replace('Z', '+00:00'))
    return value.astimezone(MADRID)


def _formal_rows(rows: list[dict], start: datetime, end: datetime) -> list[dict]:
    return [row for row in rows
            if start <= datetime.fromisoformat(row['time'].replace('Z', '+00:00')) < end]


def aggregate(rows: list[dict], discharge_mw: float,
              start: datetime | None = None, end: datetime | None = None) -> dict:
    if not math.isfinite(discharge_mw) or discharge_mw <= 0:
        raise ValueError('A finite positive discharge_mw is required')
    by_time, ids = {}, set()
    for row in rows:
        t = datetime.fromisoformat(row['time'].replace('Z', '+00:00'))
        if t.tzinfo is None or t.minute % 15 or t.second or t.microsecond:
            raise ValueError('Result timestamps must be aware QH boundaries')
        t = t.astimezone(timezone.utc)
        if t in by_time or row['qh_id'] in ids:
            raise ValueError('Duplicate result QH')
        by_time[t] = row
        ids.add(row['qh_id'])
    missing_rows = 0
    if start is not None and end is not None:
        if any(t.tzinfo is None or t.minute % 15 or t.second or t.microsecond for t in (start, end)) or start >= end:
            raise ValueError('Invalid formal QH interval')
        grid = []
        t = start.astimezone(timezone.utc)
        while t < end:
            row = by_time.get(t)
            if row is None:
                missing_rows += 1
                row = dict(qh_id=t.isoformat(), time=t.isoformat(), cash=None, efc=None, status='missing_result')
            grid.append(row)
            t += timedelta(minutes=15)
        rows = grid
    monthly = defaultdict(lambda: dict(cash_eur={m: 0.0 for m in MARKETS}, valid_qh=0,
                                       total_qh=0, efc=0.0, efc_known_qh=0, calendar_complete=True))
    total = {m: 0.0 for m in MARKETS}
    valid_rows = {}
    daily = defaultdict(lambda: dict(valid_qh=0, total_qh=0))
    hourly_qhs = defaultdict(dict)
    for row in rows:
        local = _madrid_time(row)
        month = local.strftime('%Y-%m')
        item = monthly[month]
        item['total_qh'] += 1
        daily[local.date().isoformat()]['total_qh'] += 1
        if row.get('efc') is not None:
            efc = float(row['efc'])
            if not math.isfinite(efc) or efc < 0:
                raise ValueError('Invalid executed EFC')
            item['efc'] += efc
            item['efc_known_qh'] += 1
        cash = row.get('cash')
        if cash is None:
            continue
        if any(m not in cash or cash[m] is None or not math.isfinite(float(cash[m])) for m in MARKETS):
            raise ValueError('A settled QH must have six finite market cash values')
        item['valid_qh'] += 1
        daily[local.date().isoformat()]['valid_qh'] += 1
        valid_rows[row['qh_id']] = row
        for market in MARKETS:
            value = float(cash[market])
            item['cash_eur'][market] += value
            total[market] += value
        offset = int(local.utcoffset().total_seconds() // 60)
        hourly_qhs[(local.date().isoformat(), local.hour, offset)][local.minute] = cash
    for month, item in monthly.items():
        y, m = map(int, month.split('-'))
        lo = datetime(y, m, 1, tzinfo=MADRID)
        hi = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=MADRID)
        if start is not None and end is not None:
            item['calendar_complete'] = start <= lo and end >= hi
    complete_hours = []
    for (day, hour, _offset), qhs in hourly_qhs.items():
        if set(qhs) != {0, 15, 30, 45}:
            continue
        components = {m: sum(float(qhs[minute][m]) for minute in (0, 15, 30, 45)) /
                      (1000.0 * discharge_mw) for m in MARKETS}
        complete_hours.append(dict(date=day, hour=hour, quarter=(int(day[5:7])-1)//3+1, components=components))
    hours = _hourly_means(complete_hours, range(24))
    quarters = {f'Q{q}': _hourly_means([h for h in complete_hours if h['quarter'] == q], range(24))
                for q in range(1, 5)}
    monthly_hours = _monthly_hourly_means(complete_hours)
    for month in monthly:
        monthly_hours.setdefault(month, [dict(hour=h, count=0, total_kEUR_per_MW=0.) for h in range(24)])
    return dict(monthly=dict(monthly), market_eur=total, valid_rows=valid_rows,
                complete_hours=complete_hours, hours=hours, quarters=quarters,
                monthly_hours=monthly_hours, daily=dict(daily), total_eur=sum(total.values()),
                total_efc=sum(v['efc'] for v in monthly.values()),
                efc_known_qh=sum(v['efc_known_qh'] for v in monthly.values()),
                valid_qh=sum(v['valid_qh'] for v in monthly.values()), total_qh=len(rows),
                discharge_mw=discharge_mw, missing_result_qh=missing_rows,
                unknown_execution_qh=sum(r.get('cash') is None and r.get('status') != 'assumed_idle' for r in rows))


def _hourly_means(hours: list[dict], bins) -> list[dict]:
    sums = {hour: {m: 0.0 for m in MARKETS} for hour in bins}
    counts = {hour: 0 for hour in bins}
    for item in hours:
        counts[item['hour']] += 1
        for market in MARKETS:
            sums[item['hour']][market] += item['components'][market]
    return [{'hour': hour, 'count': counts[hour],
             'components': {m: sums[hour][m] / counts[hour] if counts[hour] else 0.0 for m in MARKETS}}
            for hour in bins]


def _monthly_hourly_means(hours: list[dict]) -> dict[str, list[dict]]:
    grouped = defaultdict(list)
    for item in hours:
        grouped[item['date'][:7]].append(item)
    result = {}
    for month, month_hours in sorted(grouped.items()):
        means = _hourly_means(month_hours, range(24))
        result[month] = [{'hour': row['hour'], 'count': row['count'],
                          'total_kEUR_per_MW': sum(row['components'].values())}
                         for row in means]
    return result


def _expected_qh_for_day(day: str) -> int:
    local_date = datetime.fromisoformat(day).date()
    start = datetime.combine(local_date, datetime.min.time(), tzinfo=MADRID)
    end = datetime.combine(local_date.fromordinal(local_date.toordinal() + 1),
                           datetime.min.time(), tzinfo=MADRID)
    return int((end.astimezone(ZoneInfo('UTC')) - start.astimezone(ZoneInfo('UTC'))).total_seconds() / 900)


def _scale_series(rows: list[dict], factor: float) -> list[dict]:
    return [{'hour': row['hour'], 'count': row['count'],
             'components': {m: row['components'][m] * factor for m in MARKETS}}
            for row in rows]


def _nice_tick_step(span: float) -> int:
    target = max(span / 10.0, 5.0)
    magnitude = 10 ** math.floor(math.log10(target))
    for multiplier in (1, 2, 5, 10):
        step = multiplier * magnitude
        if step >= target:
            return int(step)
    return int(10 * magnitude)


def _rolling_12m(months: dict, discharge_mw: float) -> list[dict]:
    available = set(months)
    results = []
    for end_month in sorted(available):
        year, month = map(int, end_month.split('-'))
        end_index = year * 12 + month - 1
        window = []
        for index in range(end_index - 11, end_index + 1):
            window_year, month_index = divmod(index, 12)
            window.append(f'{window_year:04d}-{month_index + 1:02d}')
        if not all(key in available and months[key].get('calendar_complete', True)
                   and months[key].get('valid_qh', 1) > 0 for key in window):
            continue
        total_eur = sum(sum(months[key]['cash_eur'].values()) for key in window)
        results.append({'month': end_month, 'window_start': window[0], 'window_end': end_month,
                        'total_eur': total_eur, 'kEUR': total_eur / 1000,
                        'kEUR_per_MW': total_eur / (1000 * discharge_mw),
                        'valid_qh': sum(months[k].get('valid_qh', 0) for k in window),
                        'total_qh': sum(months[k].get('total_qh', 0) for k in window)})
    return results


def _rolling_12m_svg(rows: list[dict], path: Path,
                     v1_rows: list[dict] | None = None, current_label: str = '当前情景') -> None:
    width, height = 1480, 540
    left, right, top, bottom = 98, 30, 76, 100
    plot_w, plot_h = width - left - right, height - top - bottom
    v1_rows = v1_rows or []
    v1_by_month = {r['month']: r for r in v1_rows}
    aligned_v1 = [v1_by_month[r['month']] for r in rows if r['month'] in v1_by_month]
    values = [r['kEUR_per_MW'] for r in rows] + [r['kEUR_per_MW'] for r in aligned_v1]
    low_data, high_data = min(values + [0.0]), max(values + [0.0])
    step = _nice_tick_step(max(high_data - low_data, 1.0))
    low = math.floor(low_data / step) * step
    while low + 10 * step < high_data:
        step = _nice_tick_step(10 * (step + 1))
        low = math.floor(low_data / step) * step
    high = low + 10 * step

    def y(value):
        return top + (high - value) / (high - low) * plot_h

    band = plot_w / max(len(rows), 1)
    x_by_month = {row['month']: left + band * (i + 0.5) for i, row in enumerate(rows)}
    coords = [(x_by_month[row['month']], y(row['kEUR_per_MW'])) for row in rows]
    v1_coords = [(x_by_month[row['month']], y(row['kEUR_per_MW']))
                 for row in aligned_v1]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             '<style>text{font-family:Segoe UI,Arial,sans-serif;fill:#263238}.tick{font-size:13px}.xlabel{font-size:12px}.title{font-size:21px;font-weight:600}.axis{font-size:14px}</style>',
             f'<text class="title" x="{width/2}" y="32" text-anchor="middle">{html.escape("滚动12个月单位功率收益")}</text>']
    for tick in range(11):
        value = low + tick * step
        yy = y(value)
        parts.append(f'<line x1="{left}" y1="{yy:.2f}" x2="{width-right}" y2="{yy:.2f}" stroke="#d9dfe5"/>')
        parts.append(f'<text class="tick" x="{left-10}" y="{yy+4:.2f}" text-anchor="end">{value:d}</text>')
    if not rows:
        parts.append(f'<text x="{width/2}" y="{height/2}" text-anchor="middle">不足12个合格连续自然月</text>')
    if coords:
        parts.append('<polyline fill="none" stroke="#2878a5" stroke-width="3" points="' +
                     ' '.join(f'{x:.2f},{yy:.2f}' for x, yy in coords) + '"/>')
    if v1_coords:
        parts.append('<polyline fill="none" stroke="#e87522" stroke-width="3" points="' +
                     ' '.join(f'{x:.2f},{yy:.2f}' for x, yy in v1_coords) + '"/>')
    for row, (x, yy) in zip(rows, coords):
        period = f'{row["window_start"].replace("-", "/")}–{row["window_end"].replace("-", "/")}'
        parts.append(f'<circle cx="{x:.2f}" cy="{yy:.2f}" r="5" fill="#2878a5"><title>{period}: {_fmt(row["kEUR_per_MW"])} kEUR/MW</title></circle>')
        parts.append(f'<text class="xlabel" x="{x:.2f}" y="{top+plot_h+23}" text-anchor="middle">{row["month"].replace("-", "/")}</text>')
    for row, (x, yy) in zip(aligned_v1, v1_coords):
        period = f'{row["window_start"].replace("-", "/")}–{row["window_end"].replace("-", "/")}'
        parts.append(f'<circle cx="{x:.2f}" cy="{yy:.2f}" r="5" fill="#e87522"><title>V1 100%中标；{period}: {_fmt(row["kEUR_per_MW"])} kEUR/MW</title></circle>')
    if v1_coords:
        legend_y = height - 25
        parts.extend([f'<line x1="{left+plot_w/2-170}" y1="{legend_y-4}" x2="{left+plot_w/2-140}" y2="{legend_y-4}" stroke="#2878a5" stroke-width="3"/>',
                      f'<text class="axis" x="{left+plot_w/2-132}" y="{legend_y}" >{html.escape(current_label)}</text>',
                      f'<line x1="{left+plot_w/2+72}" y1="{legend_y-4}" x2="{left+plot_w/2+102}" y2="{legend_y-4}" stroke="#e87522" stroke-width="3"/>',
                      f'<text class="axis" x="{left+plot_w/2+110}" y="{legend_y}">V1（100%中标）</text>'])
    zero = y(0)
    parts.extend([f'<line x1="{left}" y1="{zero:.2f}" x2="{width-right}" y2="{zero:.2f}" stroke="#37474f" stroke-width="1.4"/>',
                  f'<text class="axis" x="20" y="{top+plot_h/2:.1f}" text-anchor="middle" transform="rotate(-90 20 {top+plot_h/2:.1f})">收益（kEUR/MW）</text>',
                  '</svg>'])
    path.write_text('\n'.join(parts), encoding='utf-8')


def average_capacity(ledger_path: Path, valid_qh_ids: set[str], total_qh: int) -> dict:
    by_qh = defaultdict(lambda: {m: 0.0 for m in MARKETS})
    for entry in _iter_json_array(ledger_path):
        settlement = entry['settlement_type']
        if settlement in ('DA_energy', 'IDA_energy'):
            try:
                qh_id = json.loads(entry['object_id'])[-1]
            except (TypeError, json.JSONDecodeError):
                continue
            market = 'DA' if settlement == 'DA_energy' else 'ID'
            # Day-ahead and intraday ledgers can contain multiple signed
            # transactions for a delivery QH; net them before taking the mean.
            quantity = abs(float(entry['quantity']))
            direction = str(entry.get('direction', '')).lower()
            mw = -quantity if direction in ('buy', 'charge') else quantity
        else:
            qh_id = entry['object_id']
            if settlement == 'aFRR_capacity':
                market = 'cap_' + entry['direction']
                mw = abs(float(entry['quantity']))
            elif settlement == 'aFRR_activation':
                market = 'act_' + entry['direction']
                quantity = abs(float(entry['quantity']))
                unit = entry.get('quantity_unit')
                duration = float(entry.get('hours') or 0.25)
                mw = quantity / duration if unit == 'MWh' else quantity
            else:
                continue
        if qh_id in valid_qh_ids:
            by_qh[qh_id][market] += mw
    denom = max(total_qh, 1)
    averages = {market: sum(row[market] for row in by_qh.values()) / denom for market in MARKETS}
    averages['spot_net_da_id'] = sum(row['DA'] + row['ID'] for row in by_qh.values()) / denom
    averages['reserve_both_directions'] = sum(row['cap_up'] + row['cap_down']
                                               for row in by_qh.values()) / denom
    return averages


def _chart_svg(title: str, unit: str, labels: list[str], values: list[dict], path: Path,
               *, width: int = 1500, height: int = 560, bounds: tuple | None = None) -> None:
    left, right, top, bottom = 100, 28, 74, 148 if len(labels) > 24 else 122
    plot_w, plot_h = width - left - right, height - top - bottom
    lows, highs = [], []
    for item in values:
        positives = sum(max(0.0, item['components'][m]) for m in MARKETS)
        negatives = sum(min(0.0, item['components'][m]) for m in MARKETS)
        lows.append(negatives)
        highs.append(positives)
    data_low = min(lows + [0.0]) if bounds is None else bounds[0]
    data_high = max(highs + [0.0]) if bounds is None else bounds[1]
    span = max(data_high - data_low, 1.0)
    tick_step = _nice_tick_step(span)
    low = math.floor(data_low / tick_step) * tick_step
    while low + 10 * tick_step < data_high:
        tick_step = _nice_tick_step(10 * (tick_step + 1))
        low = math.floor(data_low / tick_step) * tick_step
    high = low + 10 * tick_step
    def y(v):
        return top + (high - v) / (high - low) * plot_h
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             '<style>text{font-family:Segoe UI,Arial,sans-serif;fill:#263238}.tick{font-size:13px}.xlabel{font-size:12px}.legend{font-size:13px}.title{font-size:21px;font-weight:600}.axis{font-size:14px}</style>',
             f'<text class="title" x="{width/2:.1f}" y="30" text-anchor="middle">{html.escape(title)}</text>']
    for tick in range(11):
        val = low + tick * tick_step
        yy = y(val)
        parts.append(f'<line x1="{left}" y1="{yy:.2f}" x2="{width-right}" y2="{yy:.2f}" stroke="#d9dfe5"/>')
        parts.append(f'<text class="tick" x="{left-10}" y="{yy+4:.2f}" text-anchor="end">{val:d}</text>')
    zero = y(0)
    parts.append(f'<line x1="{left}" y1="{zero:.2f}" x2="{width-right}" y2="{zero:.2f}" stroke="#37474f" stroke-width="1.4"/>')
    parts.append(f'<text class="axis" x="20" y="{top+plot_h/2:.1f}" text-anchor="middle" transform="rotate(-90 20 {top+plot_h/2:.1f})">{html.escape(unit)}</text>')
    band = plot_w / max(len(labels), 1)
    bar_w = min(band * 0.72, 45 if len(labels) > 24 else 54)
    for idx, (label, item) in enumerate(zip(labels, values)):
        cx = left + band * (idx + 0.5)
        if item.get('missing') or item.get('count') == 0:
            parts.append(f'<text class="xlabel" x="{cx:.2f}" y="{zero-8:.2f}" text-anchor="middle">无有效数据</text>')
        positive = 0.0
        negative = 0.0
        for market in MARKETS:
            val = item['components'][market]
            if val >= 0:
                y0, y1 = y(positive), y(positive + val)
                positive += val
            else:
                y0, y1 = y(negative), y(negative + val)
                negative += val
            if abs(val) > 1e-12:
                parts.append(f'<rect x="{cx-bar_w/2:.2f}" y="{min(y0,y1):.2f}" width="{bar_w:.2f}" height="{max(abs(y1-y0),0.7):.2f}" fill="{COLORS[market]}"/>')
        parts.append(f'<text class="xlabel" x="{cx:.2f}" y="{top+plot_h+23}" text-anchor="middle">{html.escape(label)}</text>')
    legend_y = height - 46
    step = plot_w / len(MARKETS)
    for i, market in enumerate(MARKETS):
        x0 = left + i * step
        parts.append(f'<rect x="{x0:.1f}" y="{legend_y}" width="14" height="14" fill="{COLORS[market]}"/>')
        parts.append(f'<text class="legend" x="{x0+20:.1f}" y="{legend_y+12}">{html.escape(LABELS_ZH[market])}</text>')
    parts.append('</svg>')
    path.write_text('\n'.join(parts), encoding='utf-8')


def _monthly_hourly_heatmap(monthly_hours: dict[str, list[dict]], path: Path) -> None:
    width, left, right, top, row_h, bottom = 1580, 112, 24, 82, 30, 94
    months = sorted(monthly_hours)
    cell_w = (width - left - right) / 24
    height = top + len(months) * row_h + bottom
    vals = [r['total_kEUR_per_MW'] for month in months for r in monthly_hours[month] if r['count']]
    scale = max((max((abs(v) for v in vals), default=0.0)), 1e-12)

    def color(value: float) -> str:
        intensity = min(abs(value) / scale, 1.0)
        end = (28, 90, 150) if value >= 0 else (180, 55, 55)
        start = (247, 249, 251)
        rgb = tuple(round(start[i] + intensity * (end[i] - start[i])) for i in range(3))
        return '#%02x%02x%02x' % rgb

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             '<style>text{font-family:Segoe UI,Arial,sans-serif;fill:#263238}.tick{font-size:12px}.cell{font-size:10px}.title{font-size:21px;font-weight:600}.axis{font-size:14px}</style>',
             f'<text class="title" x="{width/2}" y="32" text-anchor="middle">按月和小时的平均总收益热力图</text>']
    for hour in range(24):
        x = left + hour * cell_w + cell_w / 2
        parts.append(f'<text class="tick" x="{x:.1f}" y="{top-12}" text-anchor="middle">{hour}</text>')
    for ridx, month in enumerate(months):
        y = top + ridx * row_h
        parts.append(f'<text class="tick" x="{left-10}" y="{y+row_h*0.68:.1f}" text-anchor="end">{month.replace("-", "/")}</text>')
        for hour, item in enumerate(monthly_hours[month]):
            x = left + hour * cell_w
            if item['count']:
                value = item['total_kEUR_per_MW']
                parts.append(f'<rect x="{x+0.5:.1f}" y="{y+0.5:.1f}" width="{cell_w-1:.1f}" height="{row_h-1:.1f}" fill="{color(value)}" stroke="white"><title>{month} {hour:02d}:00，平均 {_fmt(value)} kEUR/MW，完整样本 {item["count"]} 小时</title></rect>')
                text_color = 'white' if abs(value) / scale > 0.55 else '#263238'
                parts.append(f'<text class="cell" x="{x+cell_w/2:.1f}" y="{y+row_h*0.67:.1f}" text-anchor="middle" style="fill:{text_color}">{_fmt(value)}</text>')
            else:
                parts.append(f'<rect x="{x+0.5:.1f}" y="{y+0.5:.1f}" width="{cell_w-1:.1f}" height="{row_h-1:.1f}" fill="#eceff1" stroke="white"><title>{month} {hour:02d}:00，无完整有效小时</title></rect>')
                parts.append(f'<text class="cell" x="{x+cell_w/2:.1f}" y="{y+row_h*.67:.1f}" text-anchor="middle">—</text>')
    y0 = top + len(months) * row_h + 38
    parts.extend([f'<text class="axis" x="{left}" y="{y0}">平均收益（kEUR/MW）</text>',
                  f'<rect x="{left+205}" y="{y0-15}" width="22" height="16" fill="#b43737"/>',
                  f'<text class="tick" x="{left+233}" y="{y0-2}">负收益</text>',
                  f'<rect x="{left+320}" y="{y0-15}" width="22" height="16" fill="#f7f9fb" stroke="#cfd8dc"/>',
                  f'<text class="tick" x="{left+348}" y="{y0-2}">接近零</text>',
                  f'<rect x="{left+435}" y="{y0-15}" width="22" height="16" fill="#1c5a96"/>',
                  f'<text class="tick" x="{left+463}" y="{y0-2}">正收益</text>', '</svg>'])
    path.write_text('\n'.join(parts), encoding='utf-8')


def _fmt(value, *, csv=False):
    if value is None:
        return '' if csv else '—'
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('Cannot format a nonfinite value')
    value = round(value, 2)
    if value == 0:
        value = 0.0
    return format(value, '.2f' if csv else ',.2f')


def _has_cash(item):
    return item.get('valid_qh', 1) > 0


def _money_table(months: dict, discharge_mw: float, years: list[int], per_mw: bool) -> str:
    divisor = 1000 * discharge_mw if per_mw else 1000
    lines = ['| 月份 | ' + ' | '.join(LABELS_ZH[m] for m in MARKETS) + ' | 合计 |',
             '|---|' + '---:|' * 7]
    for year in years:
        keys = [m for m in sorted(months) if int(m[:4]) == year]
        valid = [m for m in keys if _has_cash(months[m])]
        annual = {m: sum(months[k]['cash_eur'][m] for k in valid) / divisor for m in MARKETS}
        for key in keys:
            item = months[key]
            values = [item['cash_eur'][m] / divisor for m in MARKETS]
            label = key.replace('-', '/') + ('' if item.get('calendar_complete', True) else '（部分月）')
            lines.append('| ' + ' | '.join([label] + [_fmt(v if _has_cash(item) else None)
                                       for v in values + [sum(values)]]) + ' |')
        for label, denominator in [(f'{year}年月均（{len(valid)}个月）', len(valid)), (f'{year}年合计', 1)]:
            values = [annual[m] / max(denominator, 1) for m in MARKETS]
            lines.append('| **' + label + '** | ' + ' | '.join('**'+_fmt(v if valid else None)+'**'
                               for v in values+[sum(values)]) + ' |')
    return '单位：' + ('kEUR/MW' if per_mw else 'kEUR') + '。月均按有有效结算的月份计算；部分月不外推，覆盖见月度CSV。\n\n' + '\n'.join(lines)


def _rolling_12m_table(rows, v1_rows=None):
    v1 = {r['month']: r for r in (v1_rows or [])}
    lines = ['| 统计月份 | 对应12个月窗口 | 当前收益（kEUR/MW） | QH覆盖率 |' +
             (' V1 100%中标（kEUR/MW） | 差额：V1−当前 | 基线QH覆盖率 |' if v1_rows is not None else ''),
             '|---|---|---:|---:|' + ('---:|---:|---:|' if v1_rows is not None else '')]
    for r in rows:
        cells = [r['month'].replace('-', '/'), r['window_start']+'–'+r['window_end'], _fmt(r['kEUR_per_MW']), _coverage(r)]
        if v1_rows is not None:
            ref = v1.get(r['month'])
            cells += [_fmt(ref['kEUR_per_MW'] if ref else None),
                      _fmt(ref['kEUR_per_MW']-r['kEUR_per_MW'] if ref else None), _coverage(ref or {})]
        lines.append('| '+' | '.join(cells)+' |')
    if not rows:
        lines.append('')
        lines.append('不足12个合格连续自然月；需要覆盖完整自然月，且每月至少有有效结算记录。')
    return '\n'.join(lines)


def _coverage(item):
    return f"{100*item.get('valid_qh', 0)/item['total_qh']:.2f}%" if item.get('total_qh') else '—'


def _rolling_v1_from_monthly_csv(path: Path) -> list[dict]:
    import csv
    with path.open(encoding='utf-8-sig', newline='') as stream:
        records = {row['month']: float(row['v1_total_kEUR_per_MW'])
                   for row in csv.DictReader(stream)}
    results = []
    for end_month in sorted(records):
        year, month = map(int, end_month.split('-'))
        end_index = year * 12 + month - 1
        window = []
        for index in range(end_index - 11, end_index + 1):
            window_year, month_index = divmod(index, 12)
            window.append(f'{window_year:04d}-{month_index + 1:02d}')
        if all(key in records for key in window):
            results.append({'month': end_month, 'window_start': window[0],
                            'window_end': end_month,
                            'kEUR_per_MW': sum(records[key] for key in window)})
    return results


CONFIG_FIELDS = {'charge_mw', 'discharge_mw', 'e_min_mwh', 'e_max_mwh', 'e_initial_mwh',
                 'e_terminal_mwh', 'eta_charge', 'eta_discharge', 'reserve_limit_up_mw',
                 'reserve_limit_down_mw', 'grid_import_mw', 'grid_export_mw', 'data_scope'}
MODE_LABELS = {'full_fill': '100%中标', 'optimize': '含中标系数重新优化', 'posthoc': '固定决策事后折减'}
MODE_TEXT = {
    'full_fill': 'aFRR容量按100%中标计价，本情景未启用容量收入折减。',
    'optimize': '历史逐QH、逐方向系统实际分配容量／总报价量的代理系数进入容量收入目标后重新优化；激活收益和完整备用物理约束沿用V1。',
    'posthoc': '先按100%中标口径优化，再对容量现金流事后折减；交易决策沿用原解，没有按系数重新优化。',
}


def _load_run(run_dir):
    manifest = json.loads((run_dir/'manifest.json').read_text(encoding='utf-8'))
    summary = json.loads((run_dir/'summary.json').read_text(encoding='utf-8'))
    config = _top_level_scalars(run_dir/'solver_input.json', CONFIG_FIELDS)
    for k in CONFIG_FIELDS - {'data_scope'}:
        if not math.isfinite(float(config[k])):
            raise ValueError(f'Invalid config {k}')
    if config['discharge_mw'] <= 0 or config['e_max_mwh'] <= config['e_min_mwh']:
        raise ValueError('Invalid power or energy bounds')
    start = datetime.fromisoformat(manifest['formal_start'])
    end = datetime.fromisoformat(manifest['formal_end'])
    rows = _formal_rows(_read_rows(run_dir/'result.json'), start, end)
    data = aggregate(rows, float(config['discharge_mw']), start, end)
    mode = manifest.get('capacity_award_mode') or summary.get('capacity_award_mode')
    if mode is None:
        scenario = manifest.get('scenario', '')
        if 'capacity_award_rate_proxy' in scenario:
            mode = 'posthoc' if 'posthoc' in scenario else 'optimize'
        elif manifest.get('mode') == 'perfect_history_v1' and not manifest.get('award_rate_source'):
            mode = 'full_fill'
        else:
            raise ValueError('Cannot determine capacity award mode from metadata')
    if mode not in MODE_LABELS:
        raise ValueError('Unknown capacity award mode')
    return dict(manifest=manifest, summary=summary, config=config, start=start, end=end, data=data, mode=mode)


def _validate_baseline(current, baseline):
    for run in (current, baseline):
        if not run['manifest'].get('input_end'):
            raise ValueError('Missing comparison observation interval evidence')
    if datetime.fromisoformat(current['manifest']['input_end']) != datetime.fromisoformat(baseline['manifest']['input_end']):
        raise ValueError('Incompatible observation interval: input_end')
    if baseline['mode'] != 'full_fill':
        raise ValueError('Comparison baseline must use full_fill')
    if not baseline['summary'].get('success'):
        raise ValueError('Comparison baseline was not a successful run')
    for key in CONFIG_FIELDS:
        if current['config'][key] != baseline['config'][key]:
            raise ValueError(f'Incompatible comparison configuration: {key}')
    for key in ('start', 'end'):
        if current[key] != baseline[key]:
            raise ValueError(f'Incompatible comparison formal interval: {key}')
    for key in ('mode',):
        if not current['manifest'].get(key) or current['manifest'][key] != baseline['manifest'].get(key):
            raise ValueError('Incompatible or undocumented planning mode')
    for run in (current, baseline):
        if not run['manifest'].get('scenario') or not run['summary'].get('annual_budget'):
            raise ValueError('Missing comparison scenario or annual budget evidence')
    if current['manifest']['scenario'].split('/capacity_award_rate_proxy')[0] != baseline['manifest']['scenario'].split('/capacity_award_rate_proxy')[0]:
        raise ValueError('Incompatible calendar or activation scenario')
    if current['summary']['annual_budget'] != baseline['summary']['annual_budget']:
        raise ValueError('Incompatible annual EFC budgets')


def _annual_data(run):
    data = run['data']; months = data['monthly']; result = {}
    for year in sorted({int(k[:4]) for k in months}):
        keys = [k for k in months if int(k[:4]) == year]
        lo = max(run['start'].astimezone(MADRID), datetime(year,1,1,tzinfo=MADRID))
        hi = min(run['end'].astimezone(MADRID), datetime(year+1,1,1,tzinfo=MADRID))
        days = [d for d in data['daily'] if int(d[:4]) == year]
        complete = sum(v['total_qh'] == _expected_qh_for_day(d) and v['valid_qh'] == _expected_qh_for_day(d)
                       for d,v in data['daily'].items() if int(d[:4]) == year)
        result[year] = dict(cash_eur={m:sum(months[k]['cash_eur'][m] for k in keys) for m in MARKETS},
                            valid_qh=sum(months[k]['valid_qh'] for k in keys),
                            total_qh=sum(months[k]['total_qh'] for k in keys),
                            efc=sum(months[k]['efc'] for k in keys),
                            efc_known_qh=sum(months[k]['efc_known_qh'] for k in keys),
                            complete_days=complete,total_days=len(days),
                            year_days=(datetime(year+1,1,1)-datetime(year,1,1)).days,
                            period=f"{lo:%Y/%m/%d}–{(hi-timedelta(microseconds=1)):%Y/%m/%d}")
    return result


def _csv(headers, rows):
    import csv
    from io import StringIO
    stream=StringIO(); writer=csv.writer(stream, lineterminator='\n')
    writer.writerow(headers); writer.writerows(rows)
    return stream.getvalue()


def _monthly_csv(months, discharge_mw, years=None):
    records=[]
    for key,item in sorted(months.items()):
        values=[item['cash_eur'][m] for m in MARKETS]; values.append(sum(values))
        records.append([key, *[_fmt(v/1000 if _has_cash(item) else None,csv=True) for v in values],
            *[_fmt(v/(1000*discharge_mw) if _has_cash(item) else None,csv=True) for v in values],
            item['valid_qh'],item['total_qh'],_coverage(item),
            _fmt(item['efc'] if item.get('efc_known_qh',1) else None,csv=True),
            item.get('efc_known_qh',''),item.get('calendar_complete',True)])
    return _csv(['month',*[f'{m}_kEUR' for m in MARKETS],'total_kEUR',
                 *[f'{m}_kEUR_per_MW' for m in MARKETS],'total_kEUR_per_MW',
                 'valid_qh','total_qh','settlement_coverage','efc','efc_known_qh','calendar_complete'], records)


def _annual_csv(annual, discharge_mw):
    records=[]
    for year,item in sorted(annual.items()):
        values=[item['cash_eur'][m] for m in MARKETS]; values.append(sum(values))
        records.append([year,item['period'],*[_fmt(v/1000 if _has_cash(item) else None,csv=True) for v in values],
            *[_fmt(v/(1000*discharge_mw) if _has_cash(item) else None,csv=True) for v in values],
            item['valid_qh'],item['total_qh'],_coverage(item),item['complete_days'],item['total_days'],item['year_days'],
            _fmt(item['efc'] if item['efc_known_qh'] else None,csv=True),item['efc_known_qh']])
    return _csv(['year','period',*[f'{m}_kEUR' for m in MARKETS],'total_kEUR',
        *[f'{m}_kEUR_per_MW' for m in MARKETS],'total_kEUR_per_MW','valid_qh','total_qh','settlement_coverage',
        'complete_days','total_days','year_days','efc','efc_known_qh'],records)


def _hourly_records(rows):
    for r in rows:
        values=[r['components'][m] for m in MARKETS]; values.append(sum(values))
        yield [r['hour'],*[_fmt(v if r['count'] else None,csv=True) for v in values],r['count']]


def _hourly_csv(rows):
    return _csv(['hour',*[f'{m}_kEUR_per_MW' for m in MARKETS],'total_kEUR_per_MW','sample_hours'], _hourly_records(rows))


def _quarterly_csv(quarters):
    return _csv(['quarter','hour',*[f'{m}_kEUR_per_MW' for m in MARKETS],'total_kEUR_per_MW','sample_hours'],
                ([q,*r] for q,rows in quarters.items() for r in _hourly_records(rows)))


def _monthly_hourly_csv(monthly_hours):
    return _csv(['month','hour','average_total_kEUR_per_MW','sample_hours'],
                ([m,r['hour'],_fmt(r['total_kEUR_per_MW'] if r['count'] else None,csv=True),r['count']]
                 for m,rows in sorted(monthly_hours.items()) for r in rows))


def _rolling_12m_csv(rows, v1_rows=None):
    refs={r['month']:r for r in (v1_rows or [])}; records=[]
    for r in rows:
        ref=refs.get(r['month']); value=ref['kEUR_per_MW'] if ref else None
        records.append([r['month'],r['window_start'],r['window_end'],_fmt(r['kEUR'],csv=True),
                        _fmt(r['kEUR_per_MW'],csv=True),r['valid_qh'],r['total_qh'],_coverage(r),
                        _fmt(value,csv=True),_fmt(value-r['kEUR_per_MW'] if value is not None else None,csv=True),_coverage(ref or {})])
    return _csv(['month','window_start_month','window_end_month','rolling_total_kEUR','rolling_total_kEUR_per_MW',
                 'valid_qh','total_qh','settlement_coverage','v1_100pct_kEUR_per_MW','v1_minus_current_kEUR_per_MW','baseline_coverage'],records)


def _shares(months):
    records=[]; lines=['| 月份 | '+' | '.join(LABELS_ZH[m] for m in MARKETS)+' |', '|---|'+'---:|'*6]
    for key,item in sorted(months.items()):
        total=sum(item['cash_eur'].values())
        values=[item['cash_eur'][m]/total*100 if total and _has_cash(item) else None for m in MARKETS]
        cells=[_fmt(v)+'%' if v is not None else '不可定义' for v in values]
        lines.append('| '+key.replace('-','/')+' | '+' | '.join(cells)+' |')
        records.append([key,*[_fmt(v,csv=True) for v in values],item['valid_qh'],item['total_qh']])
    return '\n'.join(lines),_csv(['month',*[f'{m}_share_pct' for m in MARKETS],'valid_qh','total_qh'],records)


def build(run_dir: Path, output_dir: Path, v1_monthly_csv: Path | None = None,
          baseline_run_dir: Path | None = None) -> Path:
    if output_dir.exists():
        raise FileExistsError(output_dir)
    if v1_monthly_csv is not None:
        raise ValueError('CSV alone cannot verify battery and model compatibility; use --baseline-run-dir')
    run=_load_run(run_dir); data=run['data']; config=run['config']; manifest=run['manifest']; summary=run['summary']
    baseline=_load_run(baseline_run_dir) if baseline_run_dir else None
    if baseline:
        _validate_baseline(run,baseline)
    months=data['monthly']; annual=_annual_data(run); power=config['discharge_mw']; mode=run['mode']
    rolling=_rolling_12m(months,power)
    reference=_rolling_12m(baseline['data']['monthly'],power) if baseline else None
    quality=summary.get('quality',{}); unknown=max(quality.get('blocked_qh',0),data['unknown_execution_qh'])
    ledger_exists=(run_dir/'cash_ledger.json').exists()
    capacity=average_capacity(run_dir/'cash_ledger.json',set(data['valid_rows']),data['total_qh']) if ledger_exists and not unknown else None
    output_dir.mkdir(parents=True)
    for per_mw,name in [(False,'monthly_revenue_kEUR.svg'),(True,'monthly_revenue_kEUR_per_MW.svg')]:
        values=[dict(components={m:item['cash_eur'][m]/(1000*power if per_mw else 1000) for m in MARKETS},
                     missing=not _has_cash(item)) for key,item in sorted(months.items())]
        _chart_svg('月度六市场现金收益','市场现金收益（'+('kEUR/MW' if per_mw else 'kEUR')+'）',
                   [k.replace('-','/') for k in sorted(months)],values,output_dir/name)
    _rolling_12m_svg(rolling,output_dir/'rolling_12m_revenue_kEUR_per_MW.svg',reference,MODE_LABELS[mode])
    _chart_svg('全期小时平均市场现金收益','平均收益（kEUR/MW × 10⁻³）',[str(h) for h in range(24)],
               _scale_series(data['hours'],1000),output_dir/'hourly_average_kEUR_per_MW.svg')
    _monthly_hourly_heatmap(data['monthly_hours'],output_dir/'monthly_hourly_heatmap_kEUR_per_MW.svg')
    quarter_values={q:_scale_series(rows,1000) for q,rows in data['quarters'].items()}
    bounds=(min([sum(min(0,v) for v in r['components'].values()) for rows in quarter_values.values() for r in rows]+[0]),
            max([sum(max(0,v) for v in r['components'].values()) for rows in quarter_values.values() for r in rows]+[0]))
    for q,values in quarter_values.items():
        _chart_svg(q+'小时平均市场现金收益','平均收益（kEUR/MW × 10⁻³）',[str(h) for h in range(24)],values,
                   output_dir/f'{q.lower()}_hourly_average_kEUR_per_MW.svg',width=1000,height=410,bounds=bounds)
    lo=run['start'].astimezone(MADRID); hi=(run['end']-timedelta(microseconds=1)).astimezone(MADRID)
    usable=config['e_max_mwh']-config['e_min_mwh']; total=data['total_eur']; valid_months=sum(_has_cash(v) for v in months.values())
    award=manifest.get('award_rate_source') or {}
    sources=sorted({str(x['indicator']) for x in manifest.get('source_files',[]) if x.get('indicator') is not None})
    report=[f'# 西班牙MILP结果展示 {power:g} MW 可用{usable:g} MWh {MODE_LABELS[mode]}','',
            f'正式统计期：{lo:%Y/%m/%d %H:%M} 至 {hi:%Y/%m/%d %H:%M}（含最后交付QH）；报告基线v1.0。',
            f'运行状态：{summary.get("success", "未记录")}；中标模式：`{mode}`；输入目录：`{run_dir.as_posix()}`。','',
            '## 假设概览','','| 项目 | 本次配置 |','|---|---|',
            f'| 正式区间与观察数据 | 内部区间 [{run["start"].isoformat()}, {run["end"].isoformat()})；输入加载至 {manifest.get("input_end","未记录")}。观察日不计正式收益 |',
            '| 时区和分辨率 | Europe/Madrid；15分钟QH；夏令时日按92／96／100个QH |',
            f'| 电池配置 | 充／放功率{config["charge_mw"]:g}/{power:g} MW；SOC边界{config["e_min_mwh"]:g}–{config["e_max_mwh"]:g} MWh；可用时长{usable/power:.2f} h |',
            f'| 初始与终点SOC | {config["e_initial_mwh"]:g}/{config["e_terminal_mwh"]:g} MWh |',
            f'| 效率和备用上限 | 充／放效率{config["eta_charge"]:.1%}/{config["eta_discharge"]:.1%}；上／下备用{config["reserve_limit_up_mw"]:g}/{config["reserve_limit_down_mw"]:g} MW |',
            f'| 来源 | eSIOS指标：{", ".join(sources) or "未记录"} |',
            f'| 系数文件 | {award.get("path","本模式未启用" if mode=="full_fill" else "未记录")}；SHA-256：{award.get("sha256","不适用" if mode=="full_fill" else "未记录")} |',
            f'| 原始字段完整QH | {quality.get("raw_field_complete_qh","未记录")} / {quality.get("formal_qh","未记录")} |',
            f'| 正式结算覆盖 | {data["valid_qh"]}/{data["total_qh"]} QH（{_coverage(data)}）；空闲桥接{quality.get("assumed_idle_hours","未记录")}小时；阻断{quality.get("blocked_qh","未记录")} QH；结果缺行{data["missing_result_qh"]} QH |',
            f'| 年度EFC预算 | {summary.get("annual_budget","未记录")}；分母为2×可用能量={2*usable:g} MWh |',
            f'| 求解器累计用时 | {_fmt(summary.get("solver_seconds"))} 秒（空值表示未记录） |',
            f'| 总运行用时 | {_fmt(summary.get("total_wall_seconds"))} 秒（空值表示未记录，含准备和输出） |','',
            '- '+MODE_TEXT[mode],
            '- 完美历史信息下的事后条件市场现金收益；两日滚动结果不代表已证明的全时域全局收益上界。',
            '- GCT余量检查采用第一阶段全额成交建模假设。容量表为计划申报／预留MW。系数是历史系统比例代理，未据此缩减激活收益或物理预留。',
            '- 收益为六市场带符号现金流合计，未扣除模型未计入的投资、运维等项目成本。缺失收益不按覆盖比例补算。','',
            '## 结果概览','','### 全期与自然年市场现金收益','',
            '| 期间 | 收益（kEUR） | 收益（kEUR/MW） |','|---|---:|---:|']
    def income_row(label,value):
        return f'| {label} | {_fmt(value/1000 if value is not None else None)} | {_fmt(value/(1000*power) if value is not None else None)} |'
    report += [income_row('全期合计',total if valid_months else None),
               income_row(f'有效结算月份月均（{valid_months}/{len(months)}个月，部分月不外推）',total/valid_months if valid_months else None)]
    for year,item in annual.items():
        label=f'{year}年 {item["period"]}；完整天{item["complete_days"]}/{item["total_days"]}；统计期/全年{item["total_days"]}/{item["year_days"]}'
        report.append(income_row(label,sum(item['cash_eur'].values()) if _has_cash(item) else None))
    report += ['', '### 最新滚动12个月市场现金收益','',
               '滚动窗口覆盖12个完整自然月，每月至少有有效结算；不代表QH全部完整，不按缺失比例外推。']
    if rolling:
        r=rolling[-1];report += ['',f'最新窗口：{r["window_start"]}–{r["window_end"]}；{_fmt(r["kEUR"])} kEUR，{_fmt(r["kEUR_per_MW"])} kEUR/MW；QH覆盖{_coverage(r)}。']
    else:
        report += ['', '不足12个合格连续自然月。']
    report += ['', '### 逐月滚动12个月收益','']
    if baseline:
        report += ['叠加同配置100%中标基线。'+('两情景分别优化，差额包含容量计价和调度变化。' if mode!='posthoc' else '当前情景沿用100%解后折减；只有执行头寸相同，才可把差额解释为纯现金折减。')+
                   '各窗口覆盖率另列；覆盖不同时差额还包含覆盖差异。']
    else:
        report += ['仅展示当前情景曲线。']
    report += ['', '![滚动12个月收益](rolling_12m_revenue_kEUR_per_MW.svg)','',_rolling_12m_table(rolling,reference),'',
               '### 等效循环次数','',
               'EFC直接汇总模型已执行记录，按各物理相位的SOC吞吐量／两倍可用能量计算；不使用QH起末净SOC差替代。它可为小数，与完整充放电事件次数不同。',
               f'已知EFC记录{data["efc_known_qh"]}/{data["total_qh"]} QH；存在未知记录时以下为已知部分累计。','',
               '| 期间 | EFC |','|---|---:|',f'| 全期已知合计 | {_fmt(data["total_efc"] if data["efc_known_qh"] else None)} |']
    efc_months=sum(v['efc_known_qh']>0 for v in months.values())
    report.append(f'| 月均（{efc_months}个有EFC记录的月份，部分月不外推） | {_fmt(data["total_efc"]/efc_months if efc_months else None)} |')
    for year,item in annual.items():
        report.append(f'| {year}年 {item["period"]}；完整天{item["complete_days"]}/{item["total_days"]}；统计期/全年{item["total_days"]}/{item["year_days"]} | {_fmt(item["efc"] if item["efc_known_qh"] else None)} |')
    report += ['', '### 六市场收益和占比','','| 市场 | kEUR | kEUR/MW | 占总现金收益 |','|---|---:|---:|---:|']
    for m in MARKETS:
        v=data['market_eur'][m];share=_fmt(v/total*100)+'%' if total and valid_months else '不可定义'
        report.append(f'| {LABELS_ZH[m]} | {_fmt(v/1000 if valid_months else None)} | {_fmt(v/(1000*power) if valid_months else None)} | {share} |')
    report += [income_row('合计',total if valid_months else None)+(' 100.00% |' if total else ' 不可定义 |'),
               '', '负收益和负占比保留，正收益市场占比之和可能超过100%；分母为0时占比不可定义。',
               '', '### 各市场平均执行功率和申报容量','','| 市场 | 平均MW | 口径 |','|---|---:|---|']
    for m in ('DA','ID','spot_net_da_id','cap_up','cap_down','act_up','act_down'):
        label=LABELS_ZH.get(m,'DA＋ID合并现货')
        definition='买卖有符号净额，售正购负' if m in ('DA','ID','spot_net_da_id') else '计划申报／预留容量' if m.startswith('cap_') else '执行MWh按时长折算MW'
        report.append(f'| {label} | {_fmt(capacity[m] if capacity else None)} | {definition} |')
    report += ['', f'分母为全部正式{data["total_qh"]}个QH；空闲桥接按0计。方向均值存在买卖抵消，各行不能相加视为电站容量分配比例。'+
               ('存在未知执行状态或缺少账本，本次全期功率均值显示空值。' if capacity is None else ''),
               '', '## 月度结果概览','','### 月度收入 kEUR','','![月度收入](monthly_revenue_kEUR.svg)','',
               '### 月度单位功率收入 kEUR/MW','','![月度单位功率收入](monthly_revenue_kEUR_per_MW.svg)','',
               '### 月度明细与自然年汇总','',_money_table(months,power,list(annual),False),'',_money_table(months,power,list(annual),True),
               '', '### 月度六市场占比','',_shares(months)[0],
               '', '## 小时级结果概览','',
               '先合计实际小时内四个有效QH，再按同一当地钟点的有效小时数取均值；重复夏令时小时分别计入。月度图使用全部有效QH，两者样本不同。',
               f'完整有效小时{len(data["complete_hours"])}；各钟点样本数见hourly.csv。整数刻度30表示0.03 kEUR/MW。','',
               '![全期小时收益](hourly_average_kEUR_per_MW.svg)','','### 月份与小时热力图','',
               '每格为当月该钟点平均总收益，单位kEUR/MW；蓝正红负、零中心；灰色破折号表示无样本。','',
               '![月份与小时收益](monthly_hourly_heatmap_kEUR_per_MW.svg)','','### 季度小时收益','',
               '跨年度相同季度合并，四图共用纵轴范围；下列月份为存在完整小时样本的月份。']
    for q in quarter_values:
        samples=[h for h in data['complete_hours'] if h['quarter']==int(q[1])]
        included=', '.join(sorted({h['date'][:7] for h in samples})) or '无样本'
        report += ['',f'#### {q}','',f'样本月份：{included}；完整有效小时：{len(samples)}。','',
                   f'![{q}小时收益]({q.lower()}_hourly_average_kEUR_per_MW.svg)']
    report += ['', '## 输出文件与口径','',
               '- monthly.csv、annual.csv：六市场金额、覆盖、EFC及完整天；monthly_market_shares.csv：月度占比。',
               '- hourly.csv、quarterly_hourly.csv、monthly_hourly_heatmap.csv：小时收益与样本数，缺样本留空。',
               '- rolling_12m.csv：窗口收益、覆盖及可选100%基线。report_manifest.json：来源、配置和报告版本。',
               '- SVG共9张；数据不足的图显示原因，历史报告保留。',
               '- 市场规则和中标系数的研究依据见仓库research中的MILP数学规格和中标率敏感性方案；报价曲线与半岛范围匹配仍为研究待确认项。']
    files={'monthly.csv':_monthly_csv(months,power),'annual.csv':_annual_csv(annual,power),
           'hourly.csv':_hourly_csv(data['hours']),'quarterly_hourly.csv':_quarterly_csv(data['quarters']),
           'monthly_hourly_heatmap.csv':_monthly_hourly_csv(data['monthly_hours']),
           'rolling_12m.csv':_rolling_12m_csv(rolling,reference),'monthly_market_shares.csv':_shares(months)[1]}
    for name,content in files.items():
        (output_dir/name).write_text(content,encoding='utf-8-sig')
    evidence=dict(report_version='1.0',run_dir=str(run_dir.resolve()),baseline_run_dir=str(baseline_run_dir.resolve()) if baseline_run_dir else None,
                  mode=mode,config=config,formal_start=str(run['start']),formal_end=str(run['end']),
                  award_rate_source=award,input_hash=manifest.get('input_hash'),
                  valid_qh=data['valid_qh'],total_qh=data['total_qh'],missing_result_qh=data['missing_result_qh'],
                  total_eur=total if valid_months else None,total_efc=data['total_efc'] if data['efc_known_qh'] else None,
                  sources=manifest.get('source_files',[]))
    (output_dir/'report_manifest.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    path=output_dir/'结果展示.md';path.write_text('\n'.join(report)+'\n',encoding='utf-8')
    return path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--baseline-run-dir',type=Path,help='same-config full_fill run, including manifest and solver input')
    parser.add_argument('--v1-monthly-csv',type=Path,help='deprecated: supply --baseline-run-dir for configuration verification')
    args=parser.parse_args()
    print(build(args.run_dir,args.output_dir,args.v1_monthly_csv,args.baseline_run_dir))


if __name__=='__main__':
    main()
