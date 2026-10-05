"""Generate sensitivity-only copies of reviewed baseline audit/report templates.
Original p=1 files and solver source are deliberately not changed.
"""
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'romania_full_run_20261002'

def transform(name,pairs):
    text=(BASE/name).read_text(encoding='utf-8')
    for old,new in pairs:
        assert text.count(old)==1,(name,old,text.count(old))
        text=text.replace(old,new)
    (HERE/name).write_text(text,encoding='utf-8')

transform('validate_full_run.py',[
    ('def validate(run_dir):','def validate(run_dir,expected_p):'),
    ('assert cfg.p_up==cfg.p_down==cfg.p_fcr==1 and not cfg.daily_p','assert expected_p in (0.6,0.8,1.) and cfg.p_up==cfg.p_down==cfg.p_fcr==expected_p and not cfg.daily_p'),
    ('fcr_capacity_eur=times(F*.25,q.cap_f),afrr_up_capacity_eur=times(u*.25,q.cap_u),afrr_down_capacity_eur=times(d*.25,q.cap_d)',
     'fcr_capacity_eur=expected_p*times(F*.25,q.cap_f),afrr_up_capacity_eur=expected_p*times(u*.25,q.cap_u),afrr_down_capacity_eur=expected_p*times(d*.25,q.cap_d)'),
    ("return dict(status='PASS',run_manifest_sha256=", "return dict(status='PASS',capacity_income_coefficient=expected_p,run_manifest_sha256="),
    ("p.add_argument('--output',type=Path,required=True);a=p.parse_args()", "p.add_argument('--output',type=Path,required=True);p.add_argument('--expected-p',type=float,required=True);a=p.parse_args()"),
    ('report=validate(a.run);','report=validate(a.run,a.expected_p);'),
    ('limit=max(0.,A-W-1e-6);','net=max(0.,A-W);limit=net-min(1e-6,net/2);')])

transform('build_result_presentation.py',[
    ("cfg=manifest['identity']['config'];P=cfg['power_mw']", "cfg=manifest['identity']['config'];P=cfg['power_mw'];p=cfg['p_up'];assert p==cfg['p_down']==cfg['p_fcr'] and p in (0.6,0.8,1.) and not cfg['daily_p']"),
    ("report=['# 罗马尼亚MILP完整测算结果：100MW / 200MWh'", "report=[f'# 罗马尼亚MILP完整测算结果：100MW / 200MWh · 容量收入系数{p:.0%}'"),
    ("['容量系数','p上调=p下调=pFCR=100%，外生现金系数；不是实测中标率']", "['容量系数',f'p上调=p下调=pFCR={p:.0%}，独立重新优化；外生现金系数，不是实测中标率']"),
    ("f'608窗均status0（按1e-4容许gap）；最大还原目标gap=", "f'{int((metrics.status==0).sum())}窗status0，{int((metrics.status==1).sum())}窗限时可行解（按1e-4容许gap）；最大还原目标gap="),
    ("'本次仅计算p=100%的单一配置，不叠加未运行的另一情景或西班牙现金。每窗为12个完整自然月，不对市场缺口按比例外推。'", "f'本报告为p={p:.0%}独立重优化情景，三情景比较另见汇总报告。每窗为12个完整自然月，不对市场缺口按比例外推。'"),
    ("'**A（假设）**：已确认代理字段、名义时表、资格/单元、p=1、三相及FCR静态机会价值仍是研究假设。API最终结算语义、真实项目资格、实际历史信息可见性和FCR频率轨迹未因本次计算而得到确认。'", "f'**A（假设）**：已确认代理字段、名义时表、资格/单元、p={p:.0%}、三相及FCR静态机会价值仍是研究假设。p仅折减容量现金，不折减物理预留或激活义务。API最终结算语义、真实项目资格、实际历史信息可见性和FCR频率轨迹未因本次计算而得到确认。'"),
    ("下调现金为负的原价格乘电量", "下调现金＝−原价格×下调激活电量"),
    ("(HERE/'es_reference').glob('*.py')", "(HERE.parent/'romania_full_run_20261002/es_reference').glob('*.py')")])
print('Generated sensitivity audit/report copies from reviewed baseline templates')
