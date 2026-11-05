"""Независимый аудит полноты сохранённых измерений перед сдачей."""
import json
import math
import re
from collections import Counter
from pathlib import Path
from results import save_json


def verify(directory):
    directory=Path(directory)
    def read(name):
        return [json.loads(line) for line in (directory/name).read_text(encoding='utf-8').splitlines()]
    rows=read('results.jsonl')
    warm=read('warmup.jsonl')
    checks=read('checks.jsonl')
    assert len(rows)==144, len(rows)
    assert len(warm)==10, len(warm)
    assert len(checks)==2
    counts=Counter((r['condition']['series'],r['condition'].get('level')) for r in rows)
    for n in [128,512,1024,2048,4096]: assert counts['input',n]==5
    for n in [16,64,256,1024]: assert counts['output',n]==5
    for series in ['load','half']:
        for c in [1,2,4]: assert counts[series,c]==16
    assert counts['cache',None]==3
    for row in rows+warm+checks:
        assert row['status']=='ok'
        assert row['output_tokens']==row['requested_output_tokens']
        assert row['prompt_tokens']==row['expected_prompt_tokens']
        assert row['t0'] <= row['t1'] <= row['tn'] <= row['received_end']
        assert row['chunk_times_s']==sorted(row['chunk_times_s'])
        assert math.isclose(row['ttft_s'],row['t1']-row['t0'])
        assert math.isclose(row['e2e_s'],row['ttft_s']+(row['output_tokens']-1)*row['tpot_s'])
    kv={}
    for name,context,slot in [('single',16384,16384),('load',16384,4096),('half',8192,2048)]:
        log=(directory/f'server_{name}.log').read_text(encoding='utf-8')
        sizes=re.findall(r'CPU KV buffer size\s*=\s*([\d.]+) MiB',log)
        assert sizes, f'Нет размера KV в {name}'
        actual=sum(map(float,sizes))
        expected=context*147456/2**20
        assert abs(actual-expected)<1, (name,actual,expected)
        assert re.search(rf'n_ctx_slot\s*=\s*{slot}\b',log), name
        kv[name]={'context_tokens':context,'slot_tokens':slot,'kv_mib_measured':actual,
                  'kv_mib_calculated':expected,'passed':True}
    result={'passed':True,'measurement_rows':len(rows),'warmups_excluded':len(warm),
            'checks':len(checks),'kv':kv,'lengths_and_arithmetic_passed':True}
    save_json(directory/'verification.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result


if __name__=='__main__':
    verify(Path('latest_run.txt').read_text(encoding='utf-8').strip())
