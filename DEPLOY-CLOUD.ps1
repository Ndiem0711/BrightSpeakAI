# Requires Git for Windows and an authenticated GitHub session.
# Pushes ONLY code and public lesson data. Never sends local .env, Gemini keys, runtime or recordings.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if(-not (Get-Command git -ErrorAction SilentlyContinue)){throw 'Chưa cài Git for Windows: https://git-scm.com/downloads/win'}
$repo='https://github.com/Ndiem0711/BrightSpeakAI'
$temp=Join-Path $env:TEMP ('brightspeak-deploy-'+[guid]::NewGuid().ToString('N'))
Write-Host 'Đang tải repository GitHub...' -ForegroundColor Cyan
& git clone --branch main --single-branch $repo $temp
if($LASTEXITCODE -ne 0){throw 'Không thể clone GitHub. Cần đăng nhập GitHub có quyền ghi vào repository.'}
try{
  foreach($name in @('app','data','scripts','cloud','ml','tests')){
    $src=Join-Path $PSScriptRoot $name
    if(Test-Path $src){
      $dst=Join-Path $temp $name
      if(Test-Path $dst){Remove-Item $dst -Recurse -Force}
      Copy-Item $src $dst -Recurse -Force
    }
  }
  foreach($name in @('.env.example','.gitignore','.dockerignore','Dockerfile','render.yaml',
      'requirements.txt','requirements-cloud.txt','AI_MODELS.txt','VERSION.txt','README.md','.python-version')){
    $src=Join-Path $PSScriptRoot $name
    if(Test-Path $src){Copy-Item $src (Join-Path $temp $name) -Force}
  }
  # Remove legacy dependency declarations from the checked-out repository.
  $obsolete=Join-Path $temp 'requirements-ml.txt'
  if(Test-Path $obsolete){Remove-Item $obsolete -Force}
  if(-not (Test-Path (Join-Path $temp 'app\main.py'))){throw 'app/main.py must be at repository root.'}
  if(-not (Test-Path (Join-Path $temp 'app\__init__.py'))){throw 'app/__init__.py is missing.'}
  # Enforce that secrets and private student data will never be pushed.
  & git -C $temp add -A
  $staged=& git -C $temp diff --cached --name-only
  if($LASTEXITCODE -ne 0){throw 'Lỗi khi kiểm tra các thay đổi.'}
  $bad=@($staged | Where-Object { $_ -match '(^|/)(GEMINI_KEY\.txt|\.env$|runtime/|logs/|\.venv/|private_recordings/|__pycache__/)' })
  if($bad.Count -gt 0){throw 'Dừng triển khai: phát hiện tệp bí mật hoặc dữ liệu riêng trong Git stage.'}
  & git -C $temp ls-files --error-unmatch 'app/main.py' *> $null
  if($LASTEXITCODE -ne 0){throw 'app/main.py is not tracked at the repository root.'}
  & git -C $temp diff --cached --quiet
  if($LASTEXITCODE -eq 0){Write-Host 'Mã nguồn đã trùng repository; không cần push.' -ForegroundColor Green;exit 0}
  Write-Host 'Danh sách tệp sẽ cập nhật:' -ForegroundColor Cyan
  $staged | Select-Object -First 25 | ForEach-Object {Write-Host $_}
  $answer=Read-Host 'Gõ YES để push lên GitHub và kích hoạt Render auto-deploy'
  if($answer -cne 'YES'){Write-Host 'Đã hủy; không thay đổi Cloud.';exit 0}
  & git -C $temp commit -m 'Publish BrightSpeakAI Gemini-only ASR with guided live conversation'
  if($LASTEXITCODE -ne 0){throw 'Git commit lỗi. Kiểm tra user.name/user.email trong Git.'}
  & git -C $temp push origin main
  if($LASTEXITCODE -ne 0){throw 'Không thể push. Kiểm tra quyền repository và branch protection.'}
  Write-Host 'Đã push mã. Render tự triển khai khi nhận commit mới.' -ForegroundColor Green
  Write-Host 'Dashboard: https://dashboard.render.com (open brightspeakai-app after Blueprint sync)'
  Write-Host 'Sau khi Deploy status=Live, kiểm tra /api/v1/system/health và chạy QA chức năng.'
}finally{
  if(Test-Path $temp){Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue}
}
