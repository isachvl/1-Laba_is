"""Короткая демонстрация для защиты на уже запущенном сервере."""
import asyncio
import json
from pathlib import Path
import yaml
from client import ModelClient
from prompts import PromptBuilder


async def main():
    endpoint=yaml.safe_load(Path('endpoint.yaml').read_text(encoding='utf-8'))
    builder=PromptBuilder(endpoint['base_url'])
    client=ModelClient(endpoint)
    try:
        messages=builder.build(1024,'defense-demo')
        row=await client.measure('demo',{'series':'demo'},messages,64,1024)
        print(json.dumps({k:v for k,v in row.items() if k not in ('messages','chunk_times_s')},
                         ensure_ascii=False,indent=2))
        if row['status']!='ok':
            raise RuntimeError(row['error'])
    finally:
        builder.close()
        await client.close()


if __name__=='__main__':
    asyncio.run(main())
