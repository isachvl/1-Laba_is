# Перенос на ноутбук с Windows

Репозиторий новой ЛР1: https://github.com/isachvl/1-Laba_is
Обратите внимание на дефис: старая ЛР0 находится в другом репозитории `1Laba_is`.

## Отправка с текущего компьютера

В PowerShell:

```powershell
cd D:\project\python\lab1
git status
git add .
git diff --cached --stat
git commit -m "Add measured results, MLflow artifacts and laptop setup"
git push -u origin main
```

В Git попадут код, тесты, текст книги, отчёт, завершённый запуск, база и артефакты MLflow.
Модель, бинарники сервера и Python-окружение не включаются: они восстанавливаются ниже.
Если GitHub потребует авторизацию, войдите в свой аккаунт. Если push отклонён из-за
новых коммитов на GitHub, сначала `git pull --rebase origin main`, затем повторите push.
При конфликте остановитесь и разберите его; `push --force` не нужен.

## Скачать на ноутбук

Для команд нужны Git и Python 3.12 (64-bit). Для простого чтения PDF они не нужны.
В PowerShell на ноутбуке:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\Documents\project\python" | Out-Null
cd "$env:USERPROFILE\Documents\project\python"
git clone https://github.com/isachvl/1-Laba_is.git lab1
cd lab1
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe prepare_laptop.py
.\.venv\Scripts\python.exe -m unittest discover -p "test_*.py"
.\.venv\Scripts\python.exe verify_results.py
```

`prepare_laptop.py` исправляет абсолютные пути MLflow для новой папки. Метрики и
исходные результаты сохраняются, а исходная база копируется в `mlflow.db.before_move`.
Перед запуском этого скрипта закройте MLflow UI и другие программы, использующие базу.

Проверка `verify_results.py` проверяет готовые данные, а не запускает модель.
В журналах и паспорте остаются исходные пути и характеристики компьютера, где были
выполнены замеры. Их нельзя выдавать за характеристики ноутбука.

## Посмотреть сохранённые результаты

Откройте `report/report.pdf` и `report/defense.md`.
Для просмотра MLflow из папки `lab1`:

```powershell
powershell -ExecutionPolicy Bypass -File .\mlflow_ui.ps1
```

В браузере: http://127.0.0.1:5000. Эксперимент `lr1`, завершённый запуск
`73012064462741d0b49154aa715757b8`, разделы `raw`, `analysis`, `report`.
Модель для просмотра отчёта, графиков и MLflow не нужна.

## Запустить модель на ноутбуке

Следующая команда скачивает ту же CPU-сборку llama.cpp и ту же модель (~2.5 ГБ),
после чего проверяет SHA-256 весов:

```powershell
.\.venv\Scripts\python.exe prepare_laptop.py --download-assets
powershell -ExecutionPolicy Bypass -File .\start_server.ps1
```

Дождитесь готовности сервера. Во второй консоли перейдите в ту же папку `lab1`:

```powershell
cd "$env:USERPROFILE\Documents\project\python\lab1"
.\.venv\Scripts\python.exe demo.py
```

Для полного повторения сначала остановите отдельный сервер (Ctrl+C), затем:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_all.ps1
```

На ноутбуке производительность будет другой. Полный прогон создаёт новую папку в
`runs`, обновляет `latest_run.txt` и пересобирает отчёт. Старые измерения сохраняются.
Ориентируйтесь на 16 ГБ RAM и несколько гигабайт свободного места; длительность
зависит от процессора. Сервер и сценарии этого проекта подготовлены для Windows x64.

В `.gitignore` разрешён только исходный завершённый запуск. Для публикации нового
запуска добавьте разрешение для его папки или используйте `git add -f runs/ИМЯ_ЗАПУСКА`.

## Обновление графиков после git pull

Остановите MLflow UI сочетанием Ctrl+C. Если prepare_laptop.py ранее изменил локальные
пути в базе, сохраните её копию перед восстановлением версии из Git:

```powershell
Copy-Item mlflow.db mlflow.db.before_graphs -Force
git restore -- mlflow.db
git pull --ff-only origin main
.\.venv\Scripts\python.exe prepare_laptop.py
.\.venv\Scripts\python.exe simplify_mlflow.py
powershell -ExecutionPolicy Bypass -File .\mlflow_ui.ps1
```

В Metrics осталось 9 основных графиков: TTFT от входа; полное время и TPOT от
длины ответа; throughput, p90 TTFT, TPOT и goodput от клиентов; p90 TTFT и TPOT
при половинном контексте. Ось Step: токены для input/output, клиенты для load/half.
Три оформленных графика отчёта остаются в Artifacts → analysis.
