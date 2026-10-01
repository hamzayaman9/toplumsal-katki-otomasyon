# Türkiye geneli kaynak haritası için 3 Codex (gpt-6-sol) ajanını paralel, arka planda başlatır.
# Çıktılar: scratchpad\codex-uni-devlet, codex-uni-vakif, codex-stk klasörlerinde harita.json + rapor.md

$base = "C:\Users\User1\AppData\Local\Temp\claude\C--Users-User1-Desktop-toplumsalkatkiotomasyon\cce9a77d-289a-47b1-ad59-e104cb320b3c\scratchpad"
$pkg = Get-AppxPackage -Name "OpenAI.Codex" | Sort-Object Version | Select-Object -Last 1
if (-not $pkg) { throw "Codex uygulaması bulunamadı" }
$cx = Join-Path $pkg.InstallLocation "app\resources\codex.exe"
if (-not (Test-Path $cx)) { throw "codex.exe bulunamadı: $cx" }

foreach ($name in "codex-uni-devlet", "codex-uni-vakif", "codex-stk") {
    $d = Join-Path $base $name
    (Get-Content "$d\gorev.md" -Raw -Encoding UTF8) + (Get-Content "$base\ortak_kurallar.md" -Raw -Encoding UTF8) |
        Out-File "$d\prompt.md" -Encoding utf8
    $cmd = "Get-Content -Raw -Encoding UTF8 '$d\prompt.md' | & '$cx' exec --skip-git-repo-check -m gpt-6-sol " +
        "-s workspace-write -c sandbox_workspace_write.network_access=true -C '$d' -o '$d\codex_son_mesaj.md' - *> '$d\codex_log.txt'"
    $p = Start-Process powershell.exe -ArgumentList "-NoProfile", "-Command", $cmd -WorkingDirectory $d -WindowStyle Hidden -PassThru
    "$name started (PID $($p.Id))"
}
Start-Sleep 5
foreach ($name in "codex-uni-devlet", "codex-uni-vakif", "codex-stk") {
    $log = Join-Path $base "$name\codex_log.txt"
    if (Test-Path $log) { "$name log OK: " + (Get-Content $log -TotalCount 1) } else { "${name}: log yok, baslamamis olabilir" }
}
