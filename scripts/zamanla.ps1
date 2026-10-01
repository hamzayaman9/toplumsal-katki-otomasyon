# Taramayı Windows Görev Zamanlayıcı'ya günde 3 kez (08:00, 13:00, 18:00) ekler.
# Kaldırmak için: Unregister-ScheduledTask -TaskName "ToplumsalKatkiTarama" -Confirm:$false

$proje = Split-Path -Parent $PSScriptRoot
$uv = (Get-Command uv).Source
$log = Join-Path $proje "data\zamanli_calisma.log"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -Command `"`$env:PYTHONIOENCODING='utf-8'; & '$uv' run python -m katki run *>> '$log'`"" `
    -WorkingDirectory $proje

$triggers = @("08:00", "13:00", "18:00") | ForEach-Object { New-ScheduledTaskTrigger -Daily -At $_ }
$ayarlar = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask -TaskName "ToplumsalKatkiTarama" -Action $action -Trigger $triggers -Settings $ayarlar `
    -Description "Ankara Üniversitesi toplumsal katkı haber taraması" -Force
