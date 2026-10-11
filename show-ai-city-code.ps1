# show-ai-city-code.ps1
param(
  [string]$Root = ".",
  [string]$OutFile = "all-ai-city-code.txt"
)

$extensions = @(
  "*.py","*.ps1","*.md","*.txt",
  "*.json","*.yml","*.yaml","*.toml",
  "*.ini","*.cfg",
  "*.html","*.css","*.js"
)

$items = Get-ChildItem -Path $Root -Recurse -File |
  Where-Object { $extensions -contains $_.Extension }

if ($OutFile -ne "") {
  "" | Out-File -FilePath $OutFile -Encoding utf8
}

foreach ($f in $items) {
  $header = "`n========== FILE: $($f.FullName) ==========`n"

  if ($OutFile -ne "") {
    $header | Out-File -Append -Encoding utf8 -FilePath $OutFile
    Get-Content $f.FullName -Raw | Out-File -Append -Encoding utf8 -FilePath $OutFile
    "`n" | Out-File -Append -Encoding utf8 -FilePath $OutFile
  }

  Write-Host $header -ForegroundColor Cyan
  Get-Content $f.FullName | ForEach-Object { Write-Host $_ }
}

if ($OutFile -ne "") {
  Write-Host "`nDone. Saved combined code to: $OutFile" -ForegroundColor Green
}
