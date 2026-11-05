"""Точный размер после chat template; используется токенизатор самого сервера."""
import httpx
from pathlib import Path


class PromptBuilder:
    def __init__(self, base_url):
        self.http = httpx.Client(base_url=base_url.removesuffix('/v1'), timeout=120)
        text = Path('data/pride_and_prejudice.txt').read_text(encoding='utf-8-sig')
        # Отбрасываем только заголовок Gutenberg, исходный файл сохраняем целиком.
        marker = '*** START OF THE PROJECT GUTENBERG EBOOK'
        if marker in text:
            text = text.split(marker, 1)[1].split('***', 1)[1]
        self.tokens = self.tokenize(text)

    def post(self, path, payload):
        response = self.http.post(path, json=payload)
        response.raise_for_status()
        return response.json()

    def tokenize(self, text):
        return self.post('/tokenize', {'content': text, 'add_special': False,
                                       'parse_special': True})['tokens']

    def count(self, messages):
        prompt = self.post('/apply-template', {'messages': messages})['prompt']
        return len(self.tokenize(prompt))

    def build(self, n, label, offset=0):
        prefix = f'{label}\nSummarize the following text in one sentence.\n'
        count = n - self.count([{'role': 'user', 'content': prefix}])
        for _ in range(20):
            body = self.post('/detokenize', {'tokens': self.tokens[offset:offset+count]})['content']
            messages = [{'role': 'user', 'content': prefix + body}]
            actual = self.count(messages)
            if actual == n:
                return messages
            count += n-actual
        raise ValueError(f'Не удалось построить запрос на {n} токенов')

    def close(self):
        self.http.close()
