"""Build the Spain full-range result analysis without loading the 1.3 GB JSON."""
from __future__ import annotations

import csv
import html
import json
import mmap
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "output/full_range"
RESULT = RUN / "ES_HISTORICAL_CONDITIONAL_ts_start__cap_old__rolling2__D.json"
OUT = ROOT / "reports"
CHARTS = OUT / "charts"
MADRID = ZoneInfo("Europe/Madrid")
RATED_MW = 100.0
EUR_PER_DISPLAY_UNIT = 1000.0 * RATED_MW  # kEUR/MW
COLORS = {
    "DA": "#2563eb",
    "IDA": "#06b6d4",
    "aFRR_capacity_up": "#f59e0b",
    "aFRR_capacity_down": "#8b5cf6",
    "aFRR_activation_up": "#ef4444",
    "aFRR_activation_down": "#10b981",
    "aFRR_up": "#f59e0b",
    "aFRR_down": "#8b5cf6",
}


def iter_pretty_array(mm: mmap.mmap, marker: str):
    marker_pos = mm.find(marker.encode("utf-8"))
    if marker_pos < 0:
        raise KeyError(marker)
    array_pos = mm.find(b"[", marker_pos)
    cursor = array_pos + 1
    while True:
        obj = mm.find(b"{", cursor)
        closing = mm.find(b"]", cursor)
        if closing >= 0 and (obj < 0 or closing < obj):
            return
        line = mm.rfind(b"\n", array_pos, obj) + 1
        indent = mm[line:obj]
        end_marker = b"\n" + indent + b"}"
        close = mm.find(end_marker, obj)
        if close < 0:
            raise ValueError(f"unterminated object in {marker}")
        end = close + len(end_marker)
        yield json.loads(mm[obj:end])
        cursor = end


def month_hour(qh_id: str) -> tuple[str, int]:
    dt = datetime.fromisoformat(qh_id.replace("Z", "+00:00")).astimezone(MADRID)
    return dt.strftime("%Y-%m"), dt.hour


def add_order(qh: dict, qh_id: str, market: str, mw: float) -> None:
    row = qh.get(qh_id)
    if row is not None:
        row[market] += mw


def parse_contract(contract_id: str) -> tuple[str, datetime, int]:
    parts = contract_id.split(":")
    kind = parts[0]
    granularity = parts[-1]
    start = datetime.fromisoformat(":".join(parts[2:-1]).replace("Z", "+00:00"))
    return kind, start, 4 if granularity == "hour" else 1


def esc(value) -> str:
    return html.escape(str(value))


def svg_start(width: int, height: int, title: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:"Microsoft YaHei","Noto Sans CJK SC",Arial,sans-serif;fill:#1f2937}.small{font-size:12px}.axis{font-size:11px;fill:#4b5563}.title{font-size:22px;font-weight:700}.subtitle{font-size:13px;fill:#6b7280}</style>',
        f'<text x="70" y="36" class="title">{esc(title)}</text>',
    ]


def write_revenue_chart(months: list[str], revenue: dict[str, dict[str, float]]) -> None:
    width, height = 1500, 700
    left, right, top, bottom = 85, 30, 90, 110
    plot_w, plot_h = width-left-right, height-top-bottom
    series = ["DA", "IDA", "aFRR_capacity_up", "aFRR_capacity_down", "aFRR_activation_up", "aFRR_activation_down"]
    positives = [sum(max(0, revenue[m][s]/EUR_PER_DISPLAY_UNIT) for s in series) for m in months]
    negatives = [sum(min(0, revenue[m][s]/EUR_PER_DISPLAY_UNIT) for s in series) for m in months]
    ymax = max(positives) * 1.08
    ymin = min(0.0, min(negatives) * 1.08)
    scale = plot_h / (ymax-ymin)
    y0 = top + ymax*scale
    out = svg_start(width, height, "月度收益及市场分解")
    for i in range(6):
        value = ymin + (ymax-ymin)*i/5
        y = top + (ymax-value)*scale
        out += [f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="#e5e7eb"/>',
                f'<text x="{left-8}" y="{y+4:.1f}" text-anchor="end" class="axis">{value:.1f}</text>']
    out.append(f'<text x="18" y="{top+plot_h/2}" transform="rotate(-90 18 {top+plot_h/2})" class="subtitle">收益（k€/MW）</text>')
    bar_w = plot_w/len(months)*0.68
    for idx, month in enumerate(months):
        x = left + (idx+0.5)*plot_w/len(months)-bar_w/2
        pos, neg = 0.0, 0.0
        for s in series:
            v = revenue[month][s]/EUR_PER_DISPLAY_UNIT
            if v >= 0:
                y = y0-(pos+v)*scale; h=v*scale; pos += v
            else:
                y = y0-neg*scale; h=(-v)*scale; neg += v
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{max(h,0.25):.1f}" fill="{COLORS[s]}"/>')
        tx = left + (idx+0.5)*plot_w/len(months)
        out.append(f'<text x="{tx:.1f}" y="{height-bottom+18}" transform="rotate(55 {tx:.1f} {height-bottom+18})" class="axis">{month}</text>')
    labels = [("DA","DA"),("IDA","IDA"),("aFRR_capacity_up","容量上调"),("aFRR_capacity_down","容量下调"),("aFRR_activation_up","激活上调"),("aFRR_activation_down","激活下调")]
    x = 415
    for key,label in labels:
        out += [f'<rect x="{x}" y="48" width="14" height="14" fill="{COLORS[key]}"/>',f'<text x="{x+20}" y="60" class="small">{label}</text>']
        x += 165
    out.append('</svg>')
    (CHARTS/"monthly_revenue_breakdown.svg").write_text("\n".join(out),encoding="utf-8")


def write_capacity_chart(months: list[str], capacity: dict[str, dict[str, float]]) -> None:
    width, height = 1500, 650
    left, right, top, bottom = 85, 30, 90, 110
    plot_w, plot_h = width-left-right, height-top-bottom
    series = ["DA", "IDA", "aFRR_up", "aFRR_down"]
    out = svg_start(width,height,"月度容量配置结构（平均绝对承诺MW归一化）")
    for pct in range(0,101,20):
        y=top+plot_h*(1-pct/100)
        out += [f'<line x1="{left}" y1="{y}" x2="{width-right}" y2="{y}" stroke="#e5e7eb"/>',f'<text x="{left-8}" y="{y+4}" text-anchor="end" class="axis">{pct}%</text>']
    bar_w=plot_w/len(months)*0.68
    for idx,m in enumerate(months):
        vals=[capacity[m][s] for s in series]; total=sum(vals)
        y=top+plot_h
        x=left+(idx+0.5)*plot_w/len(months)-bar_w/2
        for s,v in zip(series,vals):
            share=0 if total==0 else v/total
            h=share*plot_h;y-=h
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{max(h,0.25):.1f}" fill="{COLORS[s]}"/>')
        tx=left+(idx+0.5)*plot_w/len(months)
        out.append(f'<text x="{tx:.1f}" y="{height-bottom+18}" transform="rotate(55 {tx:.1f} {height-bottom+18})" class="axis">{m}</text>')
    labels=[("DA","DA"),("IDA","IDA"),("aFRR_up","aFRR上调"),("aFRR_down","aFRR下调")]
    x=650
    for key,label in labels:
        out += [f'<rect x="{x}" y="48" width="14" height="14" fill="{COLORS[key]}"/>',f'<text x="{x+20}" y="60" class="small">{label}</text>'];x+=145
    out += ['<text x="85" y="630" class="subtitle">注：先按月计算各市场平均绝对承诺MW，再归一化为结构占比；方向容量可复用，不代表四项物理互斥。</text>','</svg>']
    (CHARTS/"monthly_capacity_allocation.svg").write_text("\n".join(out),encoding="utf-8")


def blend(hex_color: str, ratio: float) -> str:
    rgb=tuple(int(hex_color[i:i+2],16) for i in (1,3,5));ratio=max(0,min(1,ratio))
    vals=tuple(round(248+(c-248)*ratio) for c in rgb)
    return '#'+''.join(f'{v:02x}' for v in vals)


def write_heatmaps(months: list[str], hourly: dict[str, dict[tuple[str,int], float]]) -> None:
    width,height=1550,1120
    out=svg_start(width,height,"各月各小时平均容量配置（马德里当地时间，MW）")
    panels=[("DA","DA平均绝对功率"),("IDA","IDA平均绝对功率"),("aFRR_up","aFRR上调容量"),("aFRR_down","aFRR下调容量")]
    cell_w,cell_h=23,20
    for pi,(key,title) in enumerate(panels):
        col,row=pi%2,pi//2
        x0=95+col*750;y0=85+row*505
        vals=[hourly[key].get((m,h),0.0) for m in months for h in range(24)]
        vmax=max(vals) or 1.0
        out.append(f'<text x="{x0}" y="{y0-16}" font-size="16" font-weight="700">{title}（0–{vmax:.1f} MW）</text>')
        for mi,m in enumerate(months):
            y=y0+mi*cell_h
            out.append(f'<text x="{x0-7}" y="{y+14}" text-anchor="end" class="axis">{m}</text>')
            for h in range(24):
                v=hourly[key].get((m,h),0.0)
                out.append(f'<rect x="{x0+h*cell_w}" y="{y}" width="{cell_w-1}" height="{cell_h-1}" fill="{blend(COLORS[key],v/vmax)}"><title>{m} {h:02d}:00 {v:.2f} MW</title></rect>')
        for h in range(0,24,2):
            out.append(f'<text x="{x0+(h+.5)*cell_w}" y="{y0+len(months)*cell_h+16}" text-anchor="middle" class="axis">{h:02d}</text>')
    out += ['<text x="95" y="1095" class="subtitle">每个格子为该月该当地小时所含有效15分钟时段的平均绝对承诺功率或备用容量。</text>','</svg>']
    (CHARTS/"monthly_hourly_capacity_heatmaps.svg").write_text("\n".join(out),encoding="utf-8")


def fmt_revenue(v: float) -> str:
    return f"{v/EUR_PER_DISPLAY_UNIT:,.2f} k€/MW"


def main() -> None:
    OUT.mkdir(exist_ok=True);CHARTS.mkdir(exist_ok=True)
    final=json.loads((RUN/"final_report.json").read_text(encoding="utf-8"))
    preflight=json.loads((RUN/"preflight.json").read_text(encoding="utf-8"))
    qh: dict[str,dict[str,float]]={}
    revenue=defaultdict(lambda:defaultdict(float))
    with RESULT.open("rb") as f:
        mm=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
        for r in iter_pretty_array(mm,'"final_reserves"'):
            qh[r["qh_id"]]={"DA":0.0,"IDA":0.0,"aFRR_up":abs(float(r["up_mw"])),"aFRR_down":abs(float(r["down_mw"]))}
        for r in iter_pretty_array(mm,'"final_orders"'):
            kind,start,count=parse_contract(r["contract_id"])
            net=float(r["sell_mw"])-float(r["buy_mw"])
            market="DA" if kind=="da" else "IDA"
            for i in range(count):
                qid=(start+timedelta(minutes=15*i)).isoformat().replace("+00:00","Z")
                add_order(qh,qid,market,net)
        for r in iter_pretty_array(mm,'"cash_ledger"'):
            settlement=r["settlement_type"]
            if settlement=="DA_energy": key="DA"
            elif settlement=="IDA_energy": key="IDA"
            elif settlement=="aFRR_capacity": key=f"aFRR_capacity_{r['direction']}"
            elif settlement=="aFRR_activation": key=f"aFRR_activation_{r['direction']}"
            else: raise ValueError(settlement)
            revenue[str(r["execution_day"])[:7]][key]+=float(r["cash_eur"])
        mm.close()
    months=sorted(revenue)
    fields=["DA","IDA","aFRR_capacity_up","aFRR_capacity_down","aFRR_activation_up","aFRR_activation_down"]
    total_revenue=sum(sum(revenue[m][s] for s in fields) for m in months)
    if abs(total_revenue-final["gross_eur"])>1e-5:
        raise AssertionError((total_revenue,final["gross_eur"]))
    if len(qh)!=final["coverage"]["common_valid_qh"]:
        raise AssertionError((len(qh),final["coverage"]["common_valid_qh"]))

    sums=defaultdict(lambda:defaultdict(float));counts=defaultdict(int)
    hour_sums=defaultdict(lambda:defaultdict(float));hour_counts=defaultdict(int)
    for qid,row in qh.items():
        month,hour=month_hour(qid);counts[month]+=1;hour_counts[(month,hour)]+=1
        for key in ("DA","IDA"):
            value=abs(row[key]);sums[month][key]+=value;hour_sums[key][(month,hour)]+=value
        for key in ("aFRR_up","aFRR_down"):
            value=row[key];sums[month][key]+=value;hour_sums[key][(month,hour)]+=value
    capacity={m:{k:sums[m][k]/counts[m] for k in ("DA","IDA","aFRR_up","aFRR_down")} for m in months}
    hourly={k:{mh:v/hour_counts[mh] for mh,v in vals.items()} for k,vals in hour_sums.items()}

    with (OUT/"monthly_revenue_breakdown.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f);w.writerow(["month","DA_kEUR_per_MW","IDA_kEUR_per_MW","aFRR_capacity_up_kEUR_per_MW","aFRR_capacity_down_kEUR_per_MW","aFRR_activation_up_kEUR_per_MW","aFRR_activation_down_kEUR_per_MW","gross_kEUR_per_MW","covered_qh","gross_kEUR_per_MW_per_covered_hour"])
        for m in months:
            gross=sum(revenue[m][s] for s in fields)
            w.writerow([m,*[revenue[m][s]/EUR_PER_DISPLAY_UNIT for s in fields],gross/EUR_PER_DISPLAY_UNIT,counts[m],gross/EUR_PER_DISPLAY_UNIT/(counts[m]*.25)])
    with (OUT/"monthly_capacity_allocation.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f);w.writerow(["month","DA_avg_abs_mw","IDA_avg_abs_mw","aFRR_up_avg_mw","aFRR_down_avg_mw","DA_share","IDA_share","aFRR_up_share","aFRR_down_share"])
        for m in months:
            vals=[capacity[m][k] for k in ("DA","IDA","aFRR_up","aFRR_down")];den=sum(vals)
            w.writerow([m,*vals,*[v/den for v in vals]])
    with (OUT/"monthly_hourly_capacity.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f);w.writerow(["month","local_hour","valid_qh","DA_avg_abs_mw","IDA_avg_abs_mw","aFRR_up_avg_mw","aFRR_down_avg_mw"])
        for m in months:
            for h in range(24):w.writerow([m,h,hour_counts[(m,h)],*[hourly[k].get((m,h),0.0) for k in ("DA","IDA","aFRR_up","aFRR_down")]])

    write_revenue_chart(months,revenue);write_capacity_chart(months,capacity);write_heatmaps(months,hourly)
    gross_by_month={m:sum(revenue[m][s] for s in fields) for m in months}
    high=max(months,key=gross_by_month.get);low=min(months,key=gross_by_month.get)
    overall={k:sum(sums[m][k] for m in months)/sum(counts.values()) for k in ("DA","IDA","aFRR_up","aFRR_down")}
    overall_den=sum(overall.values())
    peak_hours={k:max(range(24),key=lambda h:sum(hour_sums[k].get((m,h),0) for m in months)/max(1,sum(hour_counts[(m,h)] for m in months))) for k in overall}
    battery=preflight["inputs"]["ts_start__cap_old"]["battery"]
    lines=[
        "# 西班牙储能MILP全量测算结果汇总",
        "",
        "## 1. 数据区间、模型范围和主要假设",
        "",
        f"- 测算区间：马德里当地时间2025-01-01 00:00至2026-09-01 00:00（右端不含，即截至2026-08-31）。目标{final['coverage']['target_qh']:,}个15分钟时段，共同有效{final['coverage']['common_valid_qh']:,}个，覆盖率{final['coverage']['coverage_percent']:.2f}%，分为{final['coverage']['segments']}个连续数据段。",
        "- 单一情景：`ts_start + cap_old + rolling2 + D`。激活比例按时段起点映射，激活顺序为先下后上；采用两日滚动窗口，每次仅执行首日。",
        f"- 电站参数：充放电功率各{battery['charge_mw']:.0f} MW，电网进出口各{battery['grid_import_mw']:.0f} MW；SOC范围{battery['e_min_mwh']:.0f}–{battery['e_max_mwh']:.0f} MWh，初始和段末SOC均为{battery['e_initial_mwh']:.0f} MWh，充放电效率均为{battery['eta_charge']:.0%}。",
        "- 求解器：SciPy MILP/HiGHS，presolve关闭，相对MIP gap为1e-4，单窗口时限30秒，A1–A3实验优化关闭。",
        "- 完美信息条件测算：决策使用事后完整价格和激活信息；收益为条件毛收益，未扣交易费用、税费、融资成本和电池退化现金成本。",
        "- `cap_old`采用16:00/16:30容量时表。该时表的历史适用切换日期仍未证实，因此属于建模假设。",
        "- 长期滚动适配：非最终窗口预留0.543478 EFC用于段末SOC回归，并保留1e-6 EFC数值余量；没有提高年度EFC预算。边界归一均小于既有1e-5审计容差。",
        "",
        "## 2. 测算结果和月度收益分析",
        "",
        f"最终状态为`{final['result_status']}`，条件毛收益为**{fmt_revenue(final['gross_eur'])}**。收益统一按100 MW额定功率折算为k€/MW。",
        "",
        f"全区间分项为：DA {fmt_revenue(sum(revenue[m]['DA'] for m in months))}、IDA {fmt_revenue(sum(revenue[m]['IDA'] for m in months))}、aFRR容量上调 {fmt_revenue(sum(revenue[m]['aFRR_capacity_up'] for m in months))}、容量下调 {fmt_revenue(sum(revenue[m]['aFRR_capacity_down'] for m in months))}、aFRR激活上调 {fmt_revenue(sum(revenue[m]['aFRR_activation_up'] for m in months))}、激活下调 {fmt_revenue(sum(revenue[m]['aFRR_activation_down'] for m in months))}。",
        "",
        "![月度收益及市场分解](charts/monthly_revenue_breakdown.svg)",
        "",
        "下表为图中各市场收益占当月毛收益的比例，采用带符号收益计算，因此亏损市场显示负比例，其他市场占比可能相应超过100%。",
        "",
        "| 月份 | DA | IDA | 容量上调 | 容量下调 | 激活上调 | 激活下调 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for m in months:
        gross=gross_by_month[m]
        lines.append("| "+m+" | "+" | ".join(f"{revenue[m][s]/gross:.1%}" for s in fields)+" |")
    lines += [
        "",
        f"月度收益最高的是**{high}（{fmt_revenue(gross_by_month[high])}）**，最低的是**{low}（{fmt_revenue(gross_by_month[low])}）**。月度之间同时受价格、aFRR容量价格、激活情况和有效数据覆盖时数影响，因此不能仅凭月度总额判断单位时间盈利能力。",
        "",
        "| 月份 | DA | IDA | 容量上调 | 容量下调 | 激活上调 | 激活下调 | 合计 | 每有效小时收益 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for m in months:
        gross=gross_by_month[m]
        vals=" | ".join(fmt_revenue(revenue[m][s]) for s in fields)
        lines.append(f"| {m} | {vals} | **{fmt_revenue(gross)}** | {gross/EUR_PER_DISPLAY_UNIT/(counts[m]*.25):,.3f} k€/MW·h |")
    lines += [
        "",
        "## 3. 不同月份的平均容量配置",
        "",
        "容量配置按每个有效15分钟时段计算：DA和IDA取净成交功率的绝对值，aFRR分别保留上调和下调容量；先求月均MW，再将四项归一化为结构占比。由于能量头寸可以互相对冲、上下调容量具有方向复用属性，这些占比用于描述市场承诺结构，不表示四项在物理上互斥切分100 MW。",
        "",
        "![月度容量配置](charts/monthly_capacity_allocation.svg)",
        "",
        "| 月份 | DA均值MW | IDA均值MW | aFRR上调MW | aFRR下调MW | DA占比 | IDA占比 | 上调占比 | 下调占比 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for m in months:
        vals=[capacity[m][k] for k in ("DA","IDA","aFRR_up","aFRR_down")];den=sum(vals)
        shares=[v/den for v in vals]
        lines.append(f"| {m} | {vals[0]:.1f} | {vals[1]:.1f} | {vals[2]:.1f} | {vals[3]:.1f} | {shares[0]:.1%} | {shares[1]:.1%} | {shares[2]:.1%} | {shares[3]:.1%} |")
    lines += [
        "",
        f"全区间平均绝对承诺为：DA {overall['DA']:.1f} MW、IDA {overall['IDA']:.1f} MW、aFRR上调 {overall['aFRR_up']:.1f} MW、aFRR下调 {overall['aFRR_down']:.1f} MW；归一化结构分别为{overall['DA']/overall_den:.1%}、{overall['IDA']/overall_den:.1%}、{overall['aFRR_up']/overall_den:.1%}和{overall['aFRR_down']/overall_den:.1%}。",
        "",
        "## 4. 月份 × 当地小时容量配置",
        "",
        "下图按马德里当地小时聚合。每格为对应月份、对应小时内所有有效15分钟时段的平均绝对成交功率或备用容量；颜色越深表示平均分配越高。夏令时切换日按真实当地时钟处理。",
        "",
        "![月份与小时容量热力图](charts/monthly_hourly_capacity_heatmaps.svg)",
        "",
        f"全区间按小时平均的峰值时段分别为：DA约{peak_hours['DA']:02d}:00、IDA约{peak_hours['IDA']:02d}:00、aFRR上调约{peak_hours['aFRR_up']:02d}:00、aFRR下调约{peak_hours['aFRR_down']:02d}:00。具体月份可能明显偏离该全区间平均，应以热力图及`monthly_hourly_capacity.csv`为准。",
        "",
        "## 5. 结果解释、验证和限制",
        "",
        "- 636个MILP窗口全部成功，无30秒时限命中；纯求解器时间158.25秒，正式成功运行总墙钟274.54秒。最大相对gap为9.99564e-5。",
        "- 月度市场收益分项由最终现金账本重新聚合，合计与最终条件毛收益的差额小于1e-10 k€/MW；容量统计覆盖52,247个最终有效QH。",
        "- 规则事实：价格和aFRR输入沿用本地保存的OMIE、REE/eSIOS官方原始数据。研究解释：月度收益差异反映价格、激活与有效覆盖共同作用。建模假设：完美信息、cap_old时表、两日滚动、费用与退化现金未计入。",
        "- 本报告不能作为实际可执行交易收益承诺；尤其是完美信息、数据缺口和容量时表未核实会造成向上偏差。",
        "",
        "## 附件",
        "",
        "- `monthly_revenue_breakdown.csv`：月度DA、IDA及aFRR容量/激活上下调六项收益。",
        "- `monthly_capacity_allocation.csv`：月度平均容量及归一化结构。",
        "- `monthly_hourly_capacity.csv`：月份×当地小时容量明细。",
        "- `charts/`：报告使用的SVG图表。",
    ]
    (OUT/"西班牙储能MILP全量测算结果汇总.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({"report":str(OUT/"西班牙储能MILP全量测算结果汇总.md"),"qh":len(qh),"revenue":total_revenue,"months":len(months)},ensure_ascii=False))


if __name__=="__main__":
    main()
