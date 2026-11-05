"""Restore local MLflow paths; optionally download the pinned Windows server/model."""
import argparse
from contextlib import closing
import hashlib
from pathlib import Path
import shutil
import sqlite3
import urllib.request
import zipfile

MODEL_NAME = 'Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf'
MODEL_SHA256 = '2fde00ce69dd4899c70d020845e2638353015bba0fdf161b3eb965f2bca4464e'
MODEL_URL = ('https://huggingface.co/bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF/'
             'resolve/ae44f08e1392f39c0e474af10c3ff8355c8b6688/' + MODEL_NAME)
SERVER_URL = ('https://github.com/ggml-org/llama.cpp/releases/download/b12110/'
              'llama-b12110-bin-win-cpu-x64.zip')


def relocate_mlflow(root):
    root = Path(root).resolve()
    database = root / 'mlflow.db'
    if not database.exists():
        raise FileNotFoundError('mlflow.db is missing. Clone the results commit first.')
    with closing(sqlite3.connect(database)) as connection:
        experiments = connection.execute('SELECT experiment_id, artifact_location FROM experiments').fetchall()
        runs = connection.execute('SELECT run_uuid, experiment_id, artifact_uri FROM runs').fetchall()
        updates_exp = [( (root/'mlruns'/str(eid)).as_uri(), eid)
                       for eid, old in experiments if old != (root/'mlruns'/str(eid)).as_uri()]
        updates_run = [((root/'mlruns'/str(eid)/rid/'artifacts').as_uri(), rid)
                       for rid, eid, old in runs
                       if old != (root/'mlruns'/str(eid)/rid/'artifacts').as_uri()]
        if not updates_exp and not updates_run:
            print('MLflow paths already match this folder.')
            return
        backup = root/'mlflow.db.before_move'
        if not backup.exists():
            with closing(sqlite3.connect(backup)) as target:
                connection.backup(target)
        with connection:
            connection.executemany('UPDATE experiments SET artifact_location=? WHERE experiment_id=?', updates_exp)
            connection.executemany('UPDATE runs SET artifact_uri=? WHERE run_uuid=?', updates_run)
    print('MLflow artifact paths restored. Original database: mlflow.db.before_move')


def download(url, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix+'.part')
    print('Downloading:', destination.name, flush=True)
    request = urllib.request.Request(url, headers={'User-Agent': 'LR1-reproducibility'})
    with urllib.request.urlopen(request, timeout=180) as response, partial.open('wb') as f:
        shutil.copyfileobj(response, f, length=1024*1024)
    partial.replace(destination)


def download_assets(root):
    root = Path(root).resolve()
    server_dir = root/'bin'/'llama'
    if not (server_dir/'llama-server.exe').exists():
        archive = root/'bin'/'llama-b12110.zip'
        if not archive.exists():
            download(SERVER_URL, archive)
        with zipfile.ZipFile(archive) as z:
            for member in z.infolist():
                target = (server_dir/member.filename).resolve()
                if not target.is_relative_to(server_dir.resolve()):
                    raise ValueError('Archive member leaves the server folder')
            z.extractall(server_dir)
        if not (server_dir/'llama-server.exe').exists():
            raise FileNotFoundError('llama-server.exe not found after extraction')
    model = root/'models'/MODEL_NAME
    if not model.exists():
        download(MODEL_URL, model)
    with model.open('rb') as f:
        actual = hashlib.file_digest(f, 'sha256').hexdigest()
    if actual != MODEL_SHA256:
        raise ValueError(f'Model SHA-256 mismatch: {actual}. Check the file {model}')
    print('Server is present. Model SHA-256 verified.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download-assets', action='store_true', help='Download llama.cpp and ~2.5 GB GGUF weights')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    relocate_mlflow(root)
    if args.download_assets:
        download_assets(root)
