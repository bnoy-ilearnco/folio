$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
if(!$env:FOLIO_SIGN_CERT_THUMBPRINT -and !($env:FOLIO_SIGN_ENDPOINT -and $env:FOLIO_SIGN_ACCOUNT -and $env:FOLIO_SIGN_PROFILE)){
    throw 'A validated signing identity is required before building a signed release. See docs/signing.md. Never paste signing passwords, private keys or client secrets into chat.'
}
$shellPath=(Get-Process -Id $PID).Path
$script=Join-Path $PSScriptRoot 'sign-windows.ps1'
$override=@{bundle=@{windows=@{signCommand=@{cmd=$shellPath;args=@('-NoProfile','-File',$script,'%1')}}}} | ConvertTo-Json -Depth 8 -Compress
$configDir=Join-Path $projectRoot '.signing'
New-Item -ItemType Directory -Path $configDir -Force | Out-Null
$configPath=Join-Path $configDir ("folio-signing-"+[guid]::NewGuid().ToString('N')+'.json')
Set-Content -LiteralPath $configPath -Value $override -Encoding UTF8
Push-Location $projectRoot
try{
    & node 'node_modules/@tauri-apps/cli/tauri.js' build --config $configPath
    if($LASTEXITCODE -ne 0){throw 'The signed Tauri build failed.'}
    $config=Get-Content 'src-tauri/tauri.conf.json' -Raw | ConvertFrom-Json
    $artifacts=@('src-tauri/target/release/folio-desktop.exe',"src-tauri/target/release/bundle/nsis/Folio_$($config.version)_x64-setup.exe")
    foreach($file in $artifacts){
        $signature=Get-AuthenticodeSignature -LiteralPath $file
        if($signature.Status -ne 'Valid' -or !$signature.TimeStamperCertificate){throw "Release verification failed: $file"}
        Write-Output "Verified signed release artifact: $file"
    }
}finally{Pop-Location;Remove-Item -LiteralPath $configPath -ErrorAction SilentlyContinue}
