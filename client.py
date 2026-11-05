"""Потоковый адаптер: сообщения -> запись results.jsonl."""
import time
from openai import AsyncOpenAI


def metrics(t0, t1, tn, n):
    return {"ttft_s": t1-t0, "tpot_s": (tn-t1)/(n-1) if n > 1 else None,
            "e2e_s": tn-t0}


class ModelClient:
    def __init__(self, endpoint):
        self.endpoint = endpoint
        self.client = AsyncOpenAI(base_url=endpoint['base_url'],
                                  api_key=endpoint['api_key'], timeout=600,
                                  max_retries=0)

    async def close(self):
        await self.client.close()

    async def measure(self, request_id, condition, messages, max_tokens,
                      expected_prompt_tokens, cache=False):
        generation = dict(self.endpoint['generation'])
        generation['max_tokens'] = max_tokens
        row = dict(id=request_id, condition=condition, messages=messages,
                   expected_prompt_tokens=expected_prompt_tokens,
                   requested_output_tokens=max_tokens, cache_prompt=cache,
                   status='error', chunk_times_s=[], text='')
        t0 = time.perf_counter()
        row['t0'] = t0
        usage, finish = None, None
        try:
            stream = await self.client.chat.completions.create(
                model=self.endpoint['model'], messages=messages, **generation,
                stream=True, stream_options={'include_usage': True},
                extra_body={'ignore_eos': True, 'cache_prompt': cache,
                            'top_k': 0, 'min_p': 0, 'repeat_penalty': 1.0})
            async with stream:
                async for chunk in stream:
                    if chunk.usage is not None:
                        usage = chunk.usage
                    if chunk.choices:
                        choice = chunk.choices[0]
                        if choice.finish_reason:
                            finish = choice.finish_reason
                        if choice.delta.content:
                            row['chunk_times_s'].append(time.perf_counter())
                            row['text'] += choice.delta.content
            row['received_end'] = time.perf_counter()
            if usage is None or not row['chunk_times_s']:
                raise ValueError('Нет usage или непустых фрагментов текста')
            row.update(prompt_tokens=usage.prompt_tokens,
                       output_tokens=usage.completion_tokens, finish_reason=finish,
                       t1=row['chunk_times_s'][0], tn=row['chunk_times_s'][-1])
            row.update(metrics(t0, row['t1'], row['tn'], row['output_tokens']))
            if row['output_tokens'] != max_tokens:
                raise ValueError(f"Длина ответа {row['output_tokens']} != {max_tokens}")
            if row['prompt_tokens'] != expected_prompt_tokens:
                raise ValueError(f"Длина запроса {row['prompt_tokens']} != {expected_prompt_tokens}")
            row['status'] = 'ok'
        except Exception as exc:
            row['received_end'] = time.perf_counter()
            row['error'] = repr(exc)
        return row
