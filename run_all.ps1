$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
$python=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $python -m unittest discover -p "test_*.py"
if ($LASTEXITCODE -ne 0) { throw 'Проверка метрик не прошла' }
& $python -u experiment.py
if ($LASTEXITCODE -ne 0) { throw 'Опыты не завершены: смотрите runs и журналы' }
& $python verify_results.py
if ($LASTEXITCODE -ne 0) { throw 'Проверка полноты результатов не прошла' }
& $python analyze.py
if ($LASTEXITCODE -ne 0) { throw 'Ошибка анализа' }
& $python make_report.py
if ($LASTEXITCODE -ne 0) { throw 'Ошибка отчёта' }
Write-Host 'Готово. Отчёт: report\report.pdf; запуск: latest_run.txt'
