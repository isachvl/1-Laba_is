"""Experiment из каркаса ЛР0: конфигурация, метаданные, Results, MLflow."""
import asyncio
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4
import httpx
import mlflow
import psutil
import yaml
from client import ModelClient
from prompts import PromptBuilder
from results import Results, save_json


class Experiment:
    def __init__(self, config_path='config.yaml'):
        self.config = yaml.safe_load(Path(config_path).read_text(encoding='utf-8'))
        self.endpoint = yaml.safe_load(Path('endpoint.yaml').read_text(encoding='utf-8'))
        self.run_id = datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid4().hex[:6]
        self.results = Results(Path('runs')/self.run_id)
        self.directory = self.results.run_dir
        self.server = None
        self.log = None
        self.builder = None
        self.client = None
        self.counter = 0

    def stop_server(self):
        if self.builder:
            self.builder.close()
            self.builder = None
        if self.server:
            self.server.terminate()
            try:
                self.server.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.server.kill()
                self.server.wait()
            self.server = None
        if self.log:
            self.log.close()
            self.log = None

    def start_server(self, slots, context, label):
        self.stop_server()
        # Не подменяем уже запущенный пользователем сервис.
        try:
            httpx.get('http://127.0.0.1:8080/health', timeout=2)
        except httpx.TransportError:
            pass
        else:
            raise RuntimeError('Порт 8080 уже занят. Остановите свой сервер перед опытами.')
        exe = next(Path('bin/llama').rglob('llama-server.exe')).resolve()
        model = next(Path('models').glob('*Q4_K_M.gguf')).resolve()
        command = [str(exe), '-m', str(model), '--alias', self.endpoint['model'],
                   '-c', str(context), '-np', str(slots), '-ngl', '0',
                   '-t', str(self.config['threads']), '-tb', str(self.config['threads']),
                   '-ctk', 'f16', '-ctv', 'f16', '--host', '127.0.0.1',
                   '--port', '8080', '--jinja', '--metrics', '--slots',
                   '--cache-ram', '0', '-lv', '4']
        save_json(self.directory/f'command_{label}.json', command)
        self.log = (self.directory/f'server_{label}.log').open('w', encoding='utf-8')
        self.server = subprocess.Popen(command, stdout=self.log, stderr=subprocess.STDOUT,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic()+180
        while time.monotonic() < deadline:
            if self.server.poll() is not None:
                raise RuntimeError(f'Сервер завершился, см. server_{label}.log')
            try:
                if httpx.get('http://127.0.0.1:8080/health', timeout=2).status_code == 200:
                    break
            except httpx.TransportError:
                pass
            time.sleep(1)
        else:
            raise TimeoutError('Сервер не готов за 180 с')
        self.builder = PromptBuilder(self.endpoint['base_url'])
        print(f'SERVER {label}: slots={slots}, context={context}', flush=True)

    def request(self, n, label, offset=0):
        self.counter += 1
        uid = f'{uuid4().hex}-{self.counter}'
        return uid, self.builder.build(n, uid+' '+label, offset)

    async def record(self, request, condition, n, out, cache=False, file='results.jsonl'):
        uid, messages = request
        row = await self.client.measure(uid, condition, messages, out, n, cache)
        self.results.append(row, file)
        print(f"{condition} {uid[-8:]} {row['status']} "
              f"TTFT={row.get('ttft_s',0):.3f} TPOT={row.get('tpot_s',0):.4f}", flush=True)
        if row['status'] != 'ok':
            raise RuntimeError(row['error'])
        return row

    async def warmup(self, label):
        await self.record(self.request(1024, 'warmup'), {'series': label},
                          1024, 16, file='warmup.jsonl')

    async def sequential(self, name, values, varying_input):
        await self.warmup(name)
        for value in values:
            for repeat in range(self.config['repeats']):
                n, out = (value, 16) if varying_input else (1024, value)
                await self.record(self.request(n, name),
                                  {'series': name, 'level': value, 'repeat': repeat}, n, out)

    def snapshot(self, name):
        for route in ('metrics', 'slots'):
            response = httpx.get(f'http://127.0.0.1:8080/{route}', timeout=10)
            response.raise_for_status()
            (self.directory/f'{name}_{route}.txt').write_text(response.text, encoding='utf-8')

    async def load(self, name):
        for c in self.config['concurrency']:
            # Подготовка токенизации не попадает в длительность нагрузки.
            tasks = [self.request(1024, f'{name}-{c}-{i}', offset=i*137)
                     for i in range(max(16, 4*c))]
            await self.warmup(f'{name}-{c}')
            queue = asyncio.Queue()
            for request in tasks:
                queue.put_nowait(request)
            self.snapshot(f'{name}_{c}_before')
            async def worker():
                while True:
                    try:
                        request = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        return
                    await self.record(request, {'series': name, 'level': c}, 1024, 128)
            await asyncio.gather(*(worker() for _ in range(c)))
            self.snapshot(f'{name}_{c}_after')

    async def run(self):
        for name in ('config.yaml', 'endpoint.yaml', 'hypothesis.md'):
            shutil.copy2(name, self.directory/name)
        model = next(Path('models').glob('*.gguf'))
        print('Hashing model...', flush=True)
        with model.open('rb') as f:
            model_hash = hashlib.file_digest(f, 'sha256').hexdigest()
        metadata = {'status': 'running', 'started': datetime.now().astimezone().isoformat(),
                    'python': sys.version, 'platform': platform.platform(),
                    'cpu': platform.processor(), 'physical_cores': psutil.cpu_count(logical=False),
                    'logical_cores': psutil.cpu_count(), 'ram_bytes': psutil.virtual_memory().total,
                    'threads': self.config['threads'], 'device': 'CPU; -ngl 0',
                    'model_sha256': model_hash, 'model_bytes': model.stat().st_size,
                    'model_revision': 'ae44f08e1392f39c0e474af10c3ff8355c8b6688',
                    'model_repo': 'bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF',
                    'source_lab0_commit': subprocess.check_output(
                        ['git', '-C', '../lab0', 'rev-parse', 'HEAD'], text=True).strip(),
                    'code_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in Path('.').glob('*.py')}}
        self.results.save_metadata(metadata)
        data = Path('data/pride_and_prejudice.txt')
        save_json('data/manifest.json', {'source': 'https://www.gutenberg.org/ebooks/1342.txt.utf-8',
                  'file': str(data), 'sha256': hashlib.sha256(data.read_bytes()).hexdigest(),
                  'bytes': data.stat().st_size, 'tokenizer': 'GGUF tokenizer via llama.cpp /tokenize',
                  'prompt': 'unique label + instruction + model-tokenized excerpt',
                  'load_text_offsets': 'i*137 tokens for i in 0..15'})
        shutil.copy2('data/manifest.json', self.directory/'manifest.json')
        mlflow.set_tracking_uri('sqlite:///mlflow.db')
        mlflow.set_experiment('lr1')
        with mlflow.start_run(run_name=self.run_id) as run:
            metadata['mlflow_run_id'] = run.info.run_id
            mlflow.log_params({'profile': 'cpu', 'threads': self.config['threads'],
                               'model_sha256': model_hash, 'temperature': 0,
                               **{f'slo_{k}': v for k,v in self.config['slo'].items()}})
            try:
                self.start_server(1, self.config['context'], 'single')
                self.client = ModelClient(self.endpoint)
                await self.warmup('checks')
                req = self.request(1024, 'reproducibility')
                a = await self.record(req, {'series':'check64', 'repeat':0}, 1024, 64, file='checks.jsonl')
                b = await self.record(req, {'series':'check64', 'repeat':1}, 1024, 64, file='checks.jsonl')
                save_json(self.directory/'checks.json', {'exactly_64_tokens': True,
                          'temperature_0_texts_equal': a['text'] == b['text'],
                          'arithmetic_ttft_ms': 400, 'arithmetic_tpot_ms': 20})
                await self.sequential('input', self.config['input_lengths'], True)
                await self.warmup('cache')
                req = self.request(2048, 'prefix-cache')
                for i in range(3):
                    await self.record(req, {'series':'cache', 'repeat':i}, 2048, 16, cache=True)
                await self.sequential('output', self.config['output_lengths'], False)
                self.start_server(4, self.config['context'], 'load')
                await self.load('load')
                self.start_server(4, self.config['context']//2, 'half')
                await self.load('half')
                metadata['status'] = 'completed'
            except Exception as exc:
                metadata.update(status='failed', error=repr(exc))
                raise
            finally:
                self.stop_server()
                if self.client:
                    await self.client.close()
                metadata['finished'] = datetime.now().astimezone().isoformat()
                self.results.save_metadata(metadata)
                mlflow.log_artifacts(str(self.directory), artifact_path='raw')
                Path('latest_run.txt').write_text(str(self.directory), encoding='utf-8')
        print(f'COMPLETED {self.directory}', flush=True)


if __name__ == '__main__':
    asyncio.run(Experiment().run())
