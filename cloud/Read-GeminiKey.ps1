function Get-BrightSpeakGeminiKey {
 param([string]$Root)
 $file=Join-Path $Root 'GEMINI_KEY.txt'
 if(-not (Test-Path $file)){return ''}
 foreach($line in (Get-Content -LiteralPath $file -Encoding UTF8)){
  $v=([string]$line).Trim().Trim([char]0xFEFF)
  if(!$v -or $v.StartsWith('#')){continue}
  if($v -match '^GEMINI_API_KEY\s*=\s*(.*)$'){$v=$Matches[1].Trim()}
  elseif($v -match '^[A-Za-z_]+\s*='){continue}
  $v=$v.Trim('"').Trim([char]39)
  if($v -and $v -notmatch '\s'){return $v}
 }
 return ''
}
