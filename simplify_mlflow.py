"""Keep only nine useful metric charts in the saved LR1 run."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path

KEEP = {
    'input_ttft_median',
    'output_e2e_median', 'output_tpot_median',
    'load_output_tokens_s', 'load_ttft_p90', 'load_tpot_median', 'load_goodput',
    'half_ttft_p90', 'half_tpot_median',
}


def simplify(root):
    root = Path(root)
    run = root / (root/'latest_run.txt').read_text(encoding='utf-8').strip()
    run_id = json.loads((run/'metadata.json').read_text(encoding='utf-8'))['mlflow_run_id']
    with closing(sqlite3.connect(root/'mlflow.db', timeout=30)) as c:
        backup = root/'mlflow.db.before_graphs'
        if not backup.exists():
            with closing(sqlite3.connect(backup)) as b:
                c.backup(b)
        placeholders=','.join('?' for _ in KEEP)
        with c:
            for table in ('metrics','latest_metrics'):
                c.execute(f'DELETE FROM {table} WHERE run_uuid=? AND key NOT IN ({placeholders})',
                          (run_id,*sorted(KEEP)))
        keys={row[0] for row in c.execute('SELECT key FROM latest_metrics WHERE run_uuid=?',(run_id,))}
        assert keys==KEEP, keys
    print('MLflow: 9 key metric charts retained; raw records and artifacts preserved.')


if __name__=='__main__':
    simplify(Path(__file__).resolve().parent)
