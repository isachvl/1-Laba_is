param([int]$Slots=4, [int]$Context=16384)
$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
& "$PSScriptRoot\bin\llama\llama-server.exe" -m "$PSScriptRoot\models\Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf" --alias qwen3-4b-instruct-2507 -c $Context -np $Slots -ngl 0 -t 8 -tb 8 -ctk f16 -ctv f16 --host 127.0.0.1 --port 8080 --jinja --metrics --slots --cache-ram 0 -lv 4
exit $LASTEXITCODE
