"""Compare the new share-constrained result with immutable historical v3 p100."""
import csv,json,hashlib
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs/monthly_share_100mw_200mwh_20261004'
OLD=ROOT/'outputs/capacity_sensitivity_100mw_200mwh_20261002/v3/p100_run'
FIELDS=('da_eur','fcr_capacity_eur','afrr_up_capacity_eur','afrr_down_capacity_eur','afrr_up_activation_eur','afrr_down_activation_eur')
LABELS=('DA','FCR容量','aFRR容量上调','aFRR容量下调','aFRR激活上调','aFRR激活下调')
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def aggregate(run):
    result=defaultdict(lambda:defaultdict(float))
    with (run/'executed_qh.csv').open(encoding='utf-8-sig',newline='') as f:
        for q in csv.DictReader(f):
            period=q['local_date'][:4]
            for name in (period,'全期20个月'):
                for k in FIELDS:result[name][k]+=float(q[k])
                result[name]['efc']+=float(q['efc'])
                result[name]['qh']+=1
            if '2025-09-01'<=q['local_date']<'2026-09-01':
                for k in FIELDS:result['2025-09至2026-08'][k]+=float(q[k])
    return result
def build():
    new=OUT/'run';a=read(new/'manifest.json');b=read(OLD/'manifest.json')
    assert read(new/'summary.json')['status']==read(OLD/'summary.json')['status']=='COMPLETE'
    for k in ('start','end','budgets'):assert a['identity'][k]==b['identity'][k]
    old_prices=b['input_evidence']['consumed_csv_sha256']
    assert all(a['input_evidence']['consumed_csv_sha256'][k]==v for k,v in old_prices.items())
    for k,v in b['identity']['config'].items():
        if k not in ('p_up','p_down','p_fcr','daily_p'):assert a['identity']['config'][k]==v
    old,current=aggregate(OLD),aggregate(new);records=[]
    for period in ('2025','2026','全期20个月','2025-09至2026-08'):
        for k,label in [*zip(FIELDS,LABELS),('total_eur','合计')]:
            x=sum(old[period][z] for z in FIELDS) if k=='total_eur' else old[period][k]
            y=sum(current[period][z] for z in FIELDS) if k=='total_eur' else current[period][k]
            records.append(dict(period=period,market=label,old_eur=x,new_eur=y,difference_eur=y-x,difference_pct=(y/x-1)*100 if x else None))
    with (OUT/'old_vs_monthly_share.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=records[0]);w.writeheader();w.writerows(records)
    lines=['# 月度份额版与旧 v3 100%情景对比','','两版正式区间、年度预算、储能参数、求解器时限/gap及正式/观察价格CSV字节hash一致。新版本新增需求输入及月份额限制，删除旧现金系数；旧版本系数为1。差异来自新的约束下重新优化及数值求解差异，不能解释为对旧现金按比例折减。','','金额以百万 EUR列示；2026仅1—8月，不年化。','','| 期间 | 市场 | 旧版百万EUR | 新版百万EUR | 差额百万EUR | 变化 |','|---|---|---:|---:|---:|---:|']
    for q in records:
        change='—' if q['difference_pct'] is None else f"{q['difference_pct']:.2f}%"
        lines.append(f"| {q['period']} | {q['market']} | {q['old_eur']/1e6:.3f} | {q['new_eur']/1e6:.3f} | {q['difference_eur']/1e6:.3f} | {change} |")
    lines += ['','2025-09至2026-08行为滚动12个月实际现金，除以100MW可得到EUR/MW/年；20个月总收益不能直接称为年收益。份额为研究假设，代理月及FCR激活损耗等局限沿用。']
    (OUT/'旧版与月度份额版对比.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    proof={'status':'PASS','old_manifest_sha256':digest(OLD/'manifest.json'),'new_manifest_sha256':digest(new/'manifest.json'),'same_price_csv_hashes':old_prices,'same_formal_scope_budgets_and_common_config':True,'old_total_eur':read(OLD/'summary.json')['total_eur'],'new_total_eur':read(new/'summary.json')['total_eur'],'rows':records}
    (OUT/'comparison_provenance.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in proof.items() if k.endswith('total_eur')},ensure_ascii=False))
if __name__=='__main__':build()
