param([switch]$InstallOfflineASR,[switch]$NoBrowser)
$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
$Host.UI.RawUI.WindowTitle='BrightSpeakAI'
Write-Host 'BrightSpeakAI' -ForegroundColor Cyan
Write-Host 'Khong tu dong dong cac chuong trinh khac, tu chon cong con trong.' -ForegroundColor Gray
. (Join-Path $PSScriptRoot 'cloud\Read-GeminiKey.ps1')
$key=Get-BrightSpeakGeminiKey -Root $PSScriptRoot
if(-not $key){
  Write-Host 'Chua co key; mo GEMINI_KEY.txt trong Notepad.' -ForegroundColor Yellow
  Start-Process -FilePath notepad.exe -ArgumentList @("`"$PSScriptRoot\GEMINI_KEY.txt`"") -Wait
  $key=Get-BrightSpeakGeminiKey -Root $PSScriptRoot
}
if($key){$env:GEMINI_API_KEY=$key}else{$env:GEMINI_API_KEY=''}
Remove-Variable key -ErrorAction SilentlyContinue
$env:APP_ENV='local'
$env:APP_HOST='127.0.0.1'
$env:DEMO_OTP='true'
$env:PYTHONDONTWRITEBYTECODE='1'
$exe=$null;$bootstrapArgs=@()
if(Get-Command py -ErrorAction SilentlyContinue){
  foreach($ver in @('3.12','3.11','3.13')){
    & py "-$ver" --version *> $null
    if($LASTEXITCODE -eq 0){$exe='py';$bootstrapArgs=@("-$ver");break}
  }
}
if(-not $exe -and (Get-Command python -ErrorAction SilentlyContinue)){$exe='python'}
if(-not $exe){throw 'Can cai Python 3.11+ (Add python to PATH).'}
if(-not (Test-Path '.venv\Scripts\python.exe')){
  Write-Host '[1/5] Creating virtual environment...' -ForegroundColor Yellow
  & $exe @bootstrapArgs -m venv .venv
  if($LASTEXITCODE -ne 0){throw 'Loi tao .venv'}
}
$python=(Resolve-Path '.venv\Scripts\python.exe').Path
$stamp=(Get-FileHash 'requirements.txt' -Algorithm SHA256).Hash+$(if($InstallOfflineASR){'WHISPER'}else{''})
$hashFile='.venv\requirements.sha256'
$current=if(Test-Path $hashFile){(Get-Content $hashFile -Raw).Trim()}else{''}
if($current -ne $stamp){
  Write-Host '[2/5] Installing requirements...' -ForegroundColor Yellow
  & $python -m pip install --disable-pip-version-check -r requirements.txt
  if($LASTEXITCODE -ne 0){throw 'Khong cai duoc dependencies.'}
  if($InstallOfflineASR){
    & $python -m pip install --disable-pip-version-check -r requirements-ml.txt
    if($LASTEXITCODE -ne 0){throw 'Khong cai duoc Whisper'}
  }
  Set-Content $hashFile $stamp -Encoding ASCII
}
if(-not (Test-Path '.env')){Copy-Item '.env.example' '.env'}
Write-Host '[3/5] Python preflight...' -ForegroundColor Cyan
& $python 'scripts/preflight.py'
if($LASTEXITCODE -ne 0){throw 'Python preflight failed: xem ten file va so dong trong traceback phia tren.'}
# Do NOT kill any previously running process or free the port by force.
# The user might have V7/V8/another application bound to 8765.
$preferred=8765
if($env:BRIGHTSPEAK_PREFERRED_PORT -match '^\d{4,5}$'){$preferred=[int]$env:BRIGHTSPEAK_PREFERRED_PORT}
$selected=& $python 'scripts/select_local_port.py' --host 127.0.0.1 --preferred $preferred
if($LASTEXITCODE -ne 0){throw 'Khong tim thay cong trong.'}
$port=[int](($selected | Select-Object -Last 1).Trim())
$env:APP_PORT="$port"
$url="http://127.0.0.1:$port"
if($port -ne $preferred){Write-Host "Port $preferred da co ung dung khac; BrightSpeakAI chuyen sang $port" -ForegroundColor Yellow}
New-Item -ItemType Directory -Force -Path logs | Out-Null
$out=Join-Path $PSScriptRoot 'logs\server-out.log'
$err=Join-Path $PSScriptRoot 'logs\server-error.log'
Remove-Item $out,$err -Force -ErrorAction SilentlyContinue
Write-Host "[4/5] Starting API: $url" -ForegroundColor Yellow
$server=Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$port") -WorkingDirectory $PSScriptRoot -RedirectStandardOutput $out -RedirectStandardError $err -WindowStyle Hidden -PassThru
$ready=$false
for($i=0;$i -lt 65;$i++){
  Start-Sleep -Milliseconds 400
  if($server.HasExited){break}
  try{
    $h=Invoke-RestMethod -Uri "$url/api/v1/system/health" -TimeoutSec 2
    if($h.status -eq 'ok' -and $h.version -eq '13.0.0'){$ready=$true;break}
  }catch{}
}
if(-not $ready){
  Write-Host 'Server failed. Last logs:' -ForegroundColor Red
  if(Test-Path $err){Get-Content $err -Tail 50}
  throw 'BrightSpeakAI khong the khoi dong. Xem logs\server-error.log'
}
# Store PID only after a verified successful launch.
Set-Content '.brightspeak.pid' "$($server.Id)" -Encoding ASCII
Set-Content '.brightspeak.port' "$port" -Encoding ASCII
Write-Host "[5/5] READY - $url" -ForegroundColor Green
Write-Host "Gemini: $(if($h.gemini_enabled){'Configured'}else{'Demo - hay dien GEMINI_KEY.txt'})" -ForegroundColor Cyan
Write-Host 'Chi dung tai khoan demo khi test local, khong dung du lieu HS that.' -ForegroundColor Gray
if(-not $NoBrowser){Start-Process $url}
