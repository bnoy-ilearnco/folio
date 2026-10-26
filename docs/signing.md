# Windows release signing

**Publisher decision, 26 October 2026:** pursue SignPath Foundation free OSS
signing. See [SignPath setup and current blockers](signpath/README.md), the
application draft and license audit. Foundation approval and source/data
licensing are pending. Existing packages remain unsigned. Azure instructions
below are historical reference material, not the selected route.

A public signing identity is required. No code-signing certificate was present
in CurrentUser/My or LocalMachine/My on this computer when checked. Signing
cannot be completed by inventing a publisher or generating a locally trusted
self-signed certificate. Identity verification, provider authentication and any
purchase belong to the publisher. Do not send private keys or secrets in chat.

The release workflow is ready in `scripts/build-signed.ps1`. It signs the Tauri
application and NSIS installer, requires a trusted Authenticode signature and
timestamp, and fails rather than silently producing an unsigned release.

## Existing certificate / hardware token

The code-signing certificate must be in CurrentUser/My with an accessible
private-key provider. Set its public thumbprint in your own terminal, then run:

```powershell
$env:FOLIO_SIGN_CERT_THUMBPRINT = 'YOUR_CERTIFICATE_THUMBPRINT'
./scripts/build-signed.ps1
```

The script finds SignTool in the Windows SDK, uses SHA-256 file and timestamp
digests, and defaults to DigiCert's RFC3161 timestamp service. Set
`FOLIO_TIMESTAMP_URL` if your issuer specifies a different timestamp service;
`FOLIO_SIGNTOOL` may point to your Windows SDK SignTool.

## Microsoft Artifact Signing

Local prerequisites installed: artifact-signing-cli 0.12.0, Azure CLI 2.91.0,
.NET Runtime 8.0.32 and Windows SDK SignTool 10.0.26100.0. The helper downloads
Microsoft's signing client on first authenticated use. That first signing has
not been performed; organization validation and signing credentials are pending.

### Setup for this publisher: United States organization

Microsoft lists US organizations as eligible for Public Trust. An authorized
representative must complete organization and personal identity verification
in the Azure portal. This step cannot be completed by the build scripts.

1. Sign in at https://portal.azure.com using your organization's Azure account.
   You need a Microsoft Entra tenant and an Azure subscription. Review service
   pricing before creating paid resources.
2. In Subscriptions → your subscription → Resource providers, register
   `Microsoft.CodeSigning`.
3. Search **Artifact Signing Accounts**, choose **Create**, select the
   subscription/resource group, an available region (for example East US),
   a unique account name, and the appropriate pricing tier.
4. Have an administrator assign you **Artifact Signing Identity Verifier** on
   the account. Open **Identity validations → Organization → New Identity →
   Public**. Enter the legal organization name, business identifier, address,
   website, monitored primary/secondary organization-domain emails and the
   authorized representative's exact legal name. Review the certificate subject.
5. Complete verification links and any requested identity/business documents
   directly through Microsoft's flow. Wait until validation is **Completed**.
   Microsoft estimates 1–20 business days, with additional time possible.
6. Create a **Public Trust** certificate profile using the completed identity.
   Create a Microsoft Entra app registration and service principal for the release.
   Assign **Artifact Signing Certificate Profile Signer** to the identity used
   for signing, scoped to the profile where possible.
7. Keep the account's endpoint, account name and profile name. These are the
   three non-secret settings used below. Configure signing authentication
   privately; never paste client secrets, private keys or ID documents in chat.
   The installed CLI uses service-principal authentication: configure
   `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` and `AZURE_CLIENT_SECRET` privately in
   the release terminal or secret manager. Rotate the secret according to your
   organization's policy. The signing wrapper suppresses helper output to avoid
   exposing credentials in subprocess errors.

The local build can then sign and verify both executables. Current packages
remain unsigned until that succeeds. The verification and pricing steps above
require the publisher's participation; no Azure account or paid resource has
been created by this project.

Follow Microsoft's current [setup instructions](https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart)
and [roles guide](https://learn.microsoft.com/en-us/azure/artifact-signing/concept-resources-roles).

Set up a **Public Trust** certificate profile with a validated publisher identity
in your own Azure account. Private Trust and Public Trust Test profiles do not
provide ordinary public Windows trust. Authenticate privately using your
provider's documented method. Once an account/profile exists, install the
`artifact-signing-cli` supported by Tauri and set these non-secret identifiers:

```powershell
$env:FOLIO_SIGN_ENDPOINT = 'YOUR_HTTPS_CODESIGNING_ENDPOINT'
$env:FOLIO_SIGN_ACCOUNT = 'YOUR_ACCOUNT_NAME'
$env:FOLIO_SIGN_PROFILE = 'YOUR_PUBLIC_TRUST_PROFILE'
./scripts/build-signed.ps1
```

Authentication credentials remain in the provider's supported credential flow
or the release environment, never in repository configuration. The generated
Tauri override contains only a local script path. No trust-store or App Control
policy changes are made.

A valid signature does not guarantee every organization's policy will permit
installation, nor does it guarantee immediate SmartScreen reputation.

Official references:

- https://v2.tauri.app/distribute/sign/windows/
- https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart
- https://learn.microsoft.com/en-us/azure/artifact-signing/concept-trust-models
