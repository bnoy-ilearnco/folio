param([Parameter(Mandatory=$true)][string]$File)
$ErrorActionPreference='Stop'
$target=Get-Item -LiteralPath $File
if($target.Extension -notin '.exe','.msi'){throw 'Only Windows executable/installer files may be signed.'}

if($env:FOLIO_SIGN_CERT_THUMBPRINT){
    $thumb=$env:FOLIO_SIGN_CERT_THUMBPRINT.Replace(' ','')
    if($thumb -notmatch '^[A-Fa-f0-9]{40}$'){throw 'FOLIO_SIGN_CERT_THUMBPRINT must contain the certificate thumbprint.'}
    $certificate=Get-Item -LiteralPath "Cert:\CurrentUser\My\$thumb" -ErrorAction Stop
    if(!$certificate.HasPrivateKey -or $certificate.NotAfter -le (Get-Date)){throw 'The selected signing certificate has no accessible private key, or has expired.'}
    if(!($certificate.EnhancedKeyUsageList | Where-Object {$_.ObjectId -eq '1.3.6.1.5.5.7.3.3'})){throw 'The selected certificate is not a code-signing certificate.'}
    $signTool=$env:FOLIO_SIGNTOOL
    if(!$signTool){
        $sdkRoot=Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'
        $signTool=Get-ChildItem -LiteralPath $sdkRoot -Directory | Where-Object {$_.Name -match '^10\.'} | Sort-Object Name -Descending | ForEach-Object {Join-Path $_.FullName 'x64\signtool.exe'} | Where-Object {Test-Path -LiteralPath $_} | Select-Object -First 1
    }
    if(!$signTool -or !(Test-Path -LiteralPath $signTool)){throw 'Install the Windows SDK signing tools or set FOLIO_SIGNTOOL.'}
    $timestamp=$env:FOLIO_TIMESTAMP_URL
    if(!$timestamp){$timestamp='http://timestamp.digicert.com'}
    & $signTool sign /sha1 $thumb /s My /fd SHA256 /tr $timestamp /td SHA256 /d Folio $target.FullName
    if($LASTEXITCODE -ne 0){throw 'SignTool could not sign the file.'}
} elseif($env:FOLIO_SIGN_ENDPOINT -and $env:FOLIO_SIGN_ACCOUNT -and $env:FOLIO_SIGN_PROFILE){
    $endpoint=[uri]$env:FOLIO_SIGN_ENDPOINT
    if($endpoint.Scheme -ne 'https' -or !$endpoint.Host.EndsWith('.codesigning.azure.net')){throw 'Use the HTTPS endpoint returned by Microsoft Artifact Signing.'}
    $cli=Get-Command artifact-signing-cli -ErrorAction SilentlyContinue
    if(!$cli -and (Test-Path -LiteralPath "$env:USERPROFILE/.cargo/bin/artifact-signing-cli.exe")){$cli=Get-Item -LiteralPath "$env:USERPROFILE/.cargo/bin/artifact-signing-cli.exe"}
    if(!$cli){throw 'Install artifact-signing-cli after configuring your Artifact Signing account.'}
    if(!$env:AZURE_CLIENT_ID -or !$env:AZURE_TENANT_ID -or !$env:AZURE_CLIENT_SECRET){throw 'Configure the signing service principal credentials privately in the release environment. See docs/signing.md.'}
    if(!$env:AZURE_CLI_PATH){
        $azurePaths=@("$env:ProgramFiles/Microsoft SDKs/Azure/CLI2/wbin/az.cmd","${env:ProgramFiles(x86)}/Microsoft SDKs/Azure/CLI2/wbin/az.cmd")
        $env:AZURE_CLI_PATH=$azurePaths | Where-Object {Test-Path -LiteralPath $_} | Select-Object -First 1
        if(!$env:AZURE_CLI_PATH){throw 'Install Microsoft Azure CLI or configure AZURE_CLI_PATH.'}
    }
    $cliPath=if($cli.Source){$cli.Source}else{$cli.FullName}
    # The helper may echo credential-bearing subprocess errors; suppress its output.
    & $cliPath -e $endpoint.AbsoluteUri -a $env:FOLIO_SIGN_ACCOUNT -c $env:FOLIO_SIGN_PROFILE -d Folio $target.FullName *> $null
    if($LASTEXITCODE -ne 0){throw 'Microsoft Artifact Signing could not sign the file.'}
} else {
    throw 'No signing identity configured. Set FOLIO_SIGN_CERT_THUMBPRINT for a certificate in CurrentUser/My, or FOLIO_SIGN_ENDPOINT, FOLIO_SIGN_ACCOUNT and FOLIO_SIGN_PROFILE for a validated Microsoft Artifact Signing Public Trust profile. No self-signed fallback is used.'
}

$signature=Get-AuthenticodeSignature -LiteralPath $target.FullName
if($signature.Status -ne 'Valid' -or !$signature.SignerCertificate){throw "The resulting Authenticode signature is not trusted: $($signature.Status)."}
if(!$signature.TimeStamperCertificate){throw 'The signature has no verified timestamp. Do not publish this release.'}
Write-Output "Verified trusted, timestamped signature: $($target.Name)"
