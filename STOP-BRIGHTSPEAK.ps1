$ErrorActionPreference='SilentlyContinue'
Set-Location $PSScriptRoot
if(Test-Path '.brightspeak.pid'){
  $candidate=(Get-Content '.brightspeak.pid' -Raw).Trim()
  $port=if(Test-Path '.brightspeak.port'){(Get-Content '.brightspeak.port' -Raw).Trim()}else{''}
  if($candidate -match '^\d+$'){
    $proc=Get-CimInstance Win32_Process -Filter "ProcessId = $candidate"
    $line=if($proc){[string]$proc.CommandLine}else{''}
    if($line -like '*uvicorn*app.main:app*' -and $port -match '^\d+$' -and $line.Contains("--port $port")){
      Stop-Process -Id ([int]$candidate) -Force
      Write-Host "Da dung BrightSpeak V9 PID $candidate - port $port" -ForegroundColor Green
    }else{Write-Host 'Khong dong PID vi khong xac minh duoc la BrightSpeak.' -ForegroundColor Yellow}
  }
  Remove-Item '.brightspeak.pid' -Force
  Remove-Item '.brightspeak.port' -Force
}else{Write-Host 'Khong co process V9 da duoc ghi nhan.' -ForegroundColor Yellow}
