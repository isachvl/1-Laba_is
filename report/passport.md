# Паспорт сервера ЛР1

Модель: Qwen/Qwen3-4B-Instruct-2507 (instruct, поддержка tools через Jinja).
GGUF: bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF, ревизия ae44f08e1392f39c0e474af10c3ff8355c8b6688.
Файл: Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf, Q4_K_M.
SHA-256: 2fde00ce69dd4899c70d020845e2638353015bba0fdf161b3eb965f2bca4464e.
Размер файла весов: 2497280736 байт (2.326 ГиБ).
Сервер: llama.cpp b12110, commit cd959bae9, 0.9.0-dev, Windows x86_64 CPU.
Устройство: AMD Ryzen 7 3700X, 8 физических ядер,
16 логических, RAM 15.93 ГиБ.
Потоки: 8 для prefill и decode. GPU не используется (-ngl 0).
KV-кеш: K=f16, V=f16, 36 слоёв, 8 KV-голов, размер головы 128.
Расчёт: 2*36*8*128*2 = 147456 байт/токен = 144 КиБ/токен.
Общий контекст 16384: 2304 МиБ KV; 8192: 1152 МиБ.
Лимит слота и фактический буфер проверяются по журналам ниже.
API: http://127.0.0.1:8080/v1; model=qwen3-4b-instruct-2507.
Параметры по умолчанию: endpoint.yaml. Замеры: temperature=0, top_p=1,
top_k=0, min_p=0, repeat_penalty=1, seed=42, ignore_eos=true.
cache_prompt=false в основных опытах, true только в опыте с кешем.
Дополнительный RAM-кеш запросов отключён флагом --cache-ram 0;
повторное использование префикса внутри активного слота сохраняется.
Источник каркаса ЛР0: commit aa278f2774a3156abe4e5c81691b894edca4e4bd.
Запуск: runs\20261105_032301_2ef242; начало: 2026-11-05T03:23:05.641009+07:00; окончание: 2026-11-05T04:27:55.299649+07:00.
MLflow run: 73012064462741d0b49154aa715757b8.

## single

```powershell
D:\project\python\lab1\bin\llama\llama-server.exe -m D:\project\python\lab1\models\Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf --alias qwen3-4b-instruct-2507 -c 16384 -np 1 -ngl 0 -t 8 -tb 8 -ctk f16 -ctv f16 --host 127.0.0.1 --port 8080 --jinja --metrics --slots --cache-ram 0 -lv 4
```

```text
0.00.948.390 I print_info: n_ctx_train           = 262144
0.00.948.393 I print_info: n_layer               = 36
0.00.948.393 I print_info: n_layer_all           = 36
0.00.948.407 I print_info: n_head_kv             = 8
0.00.948.410 I print_info: n_embd_head_k         = 128
0.00.948.410 I print_info: n_embd_head_v         = 128
0.00.948.434 I print_info: n_ctx_orig_yarn       = 262144
0.00.948.437 I print_info: model params          = 4.02 B
0.02.669.300 I llama_context: n_ctx                 = 16384
0.02.669.300 I llama_context: n_ctx_seq             = 16384
0.02.669.315 I llama_context: n_ctx_seq (16384) < n_ctx_train (262144) -- the full capacity of the model will not be utilized
0.03.238.811 I llama_kv_cache:        CPU KV buffer size =  2304.00 MiB
0.03.238.834 I llama_kv_cache: n_rot_k = 0, n_embd_head_k_all = 128
0.03.238.835 I llama_kv_cache: n_rot_v = 0, n_embd_head_k_all = 128
0.03.961.002 I srv    load_model: initializing, n_slots = 1, n_ctx_slot = 16384, kv_unified = 'false'
0.03.961.344 I slot   load_model: id  0 | task -1 | new slot, n_ctx = 16384
```

## load

```powershell
D:\project\python\lab1\bin\llama\llama-server.exe -m D:\project\python\lab1\models\Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf --alias qwen3-4b-instruct-2507 -c 16384 -np 4 -ngl 0 -t 8 -tb 8 -ctk f16 -ctv f16 --host 127.0.0.1 --port 8080 --jinja --metrics --slots --cache-ram 0 -lv 4
```

```text
0.00.837.039 I print_info: n_ctx_train           = 262144
0.00.837.042 I print_info: n_layer               = 36
0.00.837.043 I print_info: n_layer_all           = 36
0.00.837.061 I print_info: n_head_kv             = 8
0.00.837.064 I print_info: n_embd_head_k         = 128
0.00.837.064 I print_info: n_embd_head_v         = 128
0.00.837.088 I print_info: n_ctx_orig_yarn       = 262144
0.00.837.092 I print_info: model params          = 4.02 B
0.02.500.340 I llama_context: n_ctx                 = 16384
0.02.500.340 I llama_context: n_ctx_seq             = 4096
0.02.500.352 I llama_context: n_ctx_seq (4096) < n_ctx_train (262144) -- the full capacity of the model will not be utilized
0.03.092.226 I llama_kv_cache:        CPU KV buffer size =  2304.00 MiB
0.03.092.246 I llama_kv_cache: n_rot_k = 0, n_embd_head_k_all = 128
0.03.092.247 I llama_kv_cache: n_rot_v = 0, n_embd_head_k_all = 128
0.04.758.430 I srv    load_model: initializing, n_slots = 4, n_ctx_slot = 4096, kv_unified = 'false'
0.04.758.518 I slot   load_model: id  0 | task -1 | new slot, n_ctx = 4096
0.04.758.524 I slot   load_model: id  1 | task -1 | new slot, n_ctx = 4096
0.04.758.525 I slot   load_model: id  2 | task -1 | new slot, n_ctx = 4096
0.04.758.526 I slot   load_model: id  3 | task -1 | new slot, n_ctx = 4096
```

## half

```powershell
D:\project\python\lab1\bin\llama\llama-server.exe -m D:\project\python\lab1\models\Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf --alias qwen3-4b-instruct-2507 -c 8192 -np 4 -ngl 0 -t 8 -tb 8 -ctk f16 -ctv f16 --host 127.0.0.1 --port 8080 --jinja --metrics --slots --cache-ram 0 -lv 4
```

```text
0.00.358.989 I print_info: n_ctx_train           = 262144
0.00.358.992 I print_info: n_layer               = 36
0.00.358.992 I print_info: n_layer_all           = 36
0.00.359.007 I print_info: n_head_kv             = 8
0.00.359.011 I print_info: n_embd_head_k         = 128
0.00.359.011 I print_info: n_embd_head_v         = 128
0.00.359.033 I print_info: n_ctx_orig_yarn       = 262144
0.00.359.036 I print_info: model params          = 4.02 B
0.02.044.578 I llama_context: n_ctx                 = 8192
0.02.044.579 I llama_context: n_ctx_seq             = 2048
0.02.044.591 I llama_context: n_ctx_seq (2048) < n_ctx_train (262144) -- the full capacity of the model will not be utilized
0.02.241.430 I llama_kv_cache:        CPU KV buffer size =  1152.00 MiB
0.02.241.451 I llama_kv_cache: n_rot_k = 0, n_embd_head_k_all = 128
0.02.241.452 I llama_kv_cache: n_rot_v = 0, n_embd_head_k_all = 128
0.02.816.962 I srv    load_model: initializing, n_slots = 4, n_ctx_slot = 2048, kv_unified = 'false'
0.02.817.040 I slot   load_model: id  0 | task -1 | new slot, n_ctx = 2048
0.02.817.046 I slot   load_model: id  1 | task -1 | new slot, n_ctx = 2048
0.02.817.047 I slot   load_model: id  2 | task -1 | new slot, n_ctx = 2048
0.02.817.048 I slot   load_model: id  3 | task -1 | new slot, n_ctx = 2048
```
