"""Адаптация Results из ЛР0: неизменяемые записи и метаданные запуска."""
import json
from pathlib import Path


def save_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


class Results:
    def __init__(self, run_dir):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=False)

    def append(self, row, filename='results.jsonl'):
        with (self.run_dir/filename).open('a', encoding='utf-8') as f:
            f.write(json.dumps(row, ensure_ascii=False)+'\n')

    def save_metadata(self, metadata):
        save_json(self.run_dir/'metadata.json', metadata)
