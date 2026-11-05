"""Сводки и три графика только из сохранённых results.jsonl."""
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import yaml
from results import save_json


def analyze(directory):
    directory = Path(directory)
    rows = [json.loads(s) for s in (directory/'results.jsonl').read_text(encoding='utf-8').splitlines()]
    if any(r['status'] != 'ok' for r in rows):
        raise ValueError('Есть ошибочные запросы; отчёт нельзя считать завершённым')
    config = yaml.safe_load((directory/'config.yaml').read_text(encoding='utf-8'))
    summary = {}
    for series in ('input', 'output', 'load', 'half'):
        groups = []
        for level in sorted({r['condition']['level'] for r in rows if r['condition']['series']==series}):
            group = [r for r in rows if r['condition']['series']==series and r['condition']['level']==level]
            ttft = [r['ttft_s'] for r in group]
            tpot = [r['tpot_s'] for r in group]
            duration = max(r['received_end'] for r in group)-min(r['t0'] for r in group)
            met = dict(level=level, count=len(group), ttft_median=float(np.median(ttft)),
                       ttft_p90=float(np.percentile(ttft,90)), ttft_min=min(ttft), ttft_max=max(ttft),
                       tpot_median=float(np.median(tpot)), e2e_median=float(np.median([r['e2e_s'] for r in group])),
                       duration_s=duration,
                       output_tokens_s=sum(r['output_tokens'] for r in group)/duration,
                       requests_s=len(group)/duration,
                       goodput=sum(r['ttft_s'] <= config['slo']['ttft_s'] and
                                   r['tpot_s'] <= config['slo']['tpot_s'] for r in group)/duration)
            met['slo_pass'] = met['ttft_p90'] <= config['slo']['ttft_s'] and met['tpot_median'] <= config['slo']['tpot_s']
            met['prefill_tokens_s_proxy'] = float(np.median([r['prompt_tokens']/r['ttft_s'] for r in group]))
            groups.append(met)
        expected = 5 if series in ('input','output') else 16
        assert all(g['count']==expected for g in groups)
        summary[series] = groups
    cache = [r['ttft_s'] for r in rows if r['condition']['series']=='cache']
    summary['cache'] = {'ttft_s':cache, 'speedup_second':cache[0]/cache[1], 'speedup_third':cache[0]/cache[2]}
    out = [r for r in rows if r['condition']['series']=='output']
    slope, intercept = np.polyfit([r['output_tokens'] for r in out], [r['e2e_s'] for r in out], 1)
    pred = np.array([intercept+slope*r['output_tokens'] for r in out])
    obs = np.array([r['e2e_s'] for r in out])
    summary['fit'] = {'slope_s':float(slope), 'intercept_s':float(intercept),
                      'r2':float(1-sum((obs-pred)**2)/sum((obs-obs.mean())**2)),
                      'ttft_median':float(np.median([r['ttft_s'] for r in out])),
                      'tpot_median':float(np.median([r['tpot_s'] for r in out]))}
    for series in ('load', 'half'):
        summary[series+'_max_clients'] = max([g['level'] for g in summary[series] if g['slo_pass']], default=0)
        with (directory/f'{series}_table.csv').open('w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=list(summary[series][0]))
            writer.writeheader()
            writer.writerows(summary[series])
    save_json(directory/'summary.json', summary)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'figure.dpi':140})
    fig, ax = plt.subplots(figsize=(7.1,3.2), layout='constrained')
    groups=summary['input']; x=[g['level'] for g in groups]; y=np.array([g['ttft_median'] for g in groups])
    ax.errorbar(x,y,yerr=[y-np.array([g['ttft_min'] for g in groups]),np.array([g['ttft_max'] for g in groups])-y],fmt='o-',capsize=4)
    ax.set(xlabel='Вход, токены',ylabel='TTFT, с',title='Опыт 1: медиана и min-max, n=5')
    ax.grid(alpha=.25); fig.savefig(directory/'01_ttft.png'); plt.close(fig)
    fig,ax=plt.subplots(figsize=(7.1,3.2),layout='constrained')
    ax.scatter([r['output_tokens'] for r in out],obs,alpha=.6,label='Запросы')
    x=np.array([0,1024]); ax.plot(x,intercept+slope*x,label=f'T={intercept:.2f}+{slope:.4f}N')
    ax.set(xlabel='Ответ, токены',ylabel='Полное время, с',title='Опыт 2: длина ответа и линейная аппроксимация')
    ax.legend(); ax.grid(alpha=.25); fig.savefig(directory/'02_output.png'); plt.close(fig)
    fig,ax=plt.subplots(figsize=(7.1,3.2),layout='constrained')
    for name,label,style in [('load','Контекст 16384','o-'),('half','Контекст 8192','s--')]:
        groups=summary[name]
        ax.plot([g['output_tokens_s'] for g in groups],[g['ttft_p90'] for g in groups],style,label=label)
        if name=='load':
            for g in groups:
                ax.annotate(f"c={g['level']}",(g['output_tokens_s'],g['ttft_p90']),xytext=(4,8),textcoords='offset points')
    ax.axhline(config['slo']['ttft_s'],color='gray',linestyle=':',label='Предел TTFT')
    ax.set(xlabel='Суммарные выходные токены/с',ylabel='p90 TTFT, с',title='Опыт 3: пропускная способность и задержка')
    ax.margins(x=.12,y=.15)
    ax.legend(fontsize=8); ax.grid(alpha=.25); fig.savefig(directory/'03_load.png'); plt.close(fig)
    metadata=json.loads((directory/'metadata.json').read_text(encoding='utf-8'))
    mlflow.set_tracking_uri('sqlite:///mlflow.db')
    with mlflow.start_run(run_id=metadata['mlflow_run_id']):
        mlflow.log_metrics({'fit_slope_s':float(slope),'fit_intercept_s':float(intercept),
                            'cache_speedup':summary['cache']['speedup_second'],
                            'max_clients':summary['load_max_clients']})
        for name in ('input','output','load','half'):
            for group in summary[name]:
                mlflow.log_metrics({f'{name}_{k}':float(v) for k,v in group.items()
                                    if isinstance(v,(int,float)) and k!='level'},step=group['level'])
        for pattern in ('*.png','*table.csv','summary.json'):
            for p in directory.glob(pattern):
                mlflow.log_artifact(str(p),artifact_path='analysis')
        if (directory/'verification.json').exists():
            mlflow.log_artifact(str(directory/'verification.json'),artifact_path='analysis')
    return summary


if __name__=='__main__':
    analyze(Path('latest_run.txt').read_text(encoding='utf-8').strip())
