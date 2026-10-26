# Folio code-signing policy — draft

Status: proposed; SignPath Foundation has not approved or signed Folio.
Complete the named team and public project links before publishing this policy.

## Roles

- Project repository owner: `bnoy-ilearnco` on GitHub.
- Source reviewer(s): pending named GitHub users and Foundation approval.
- Release signing approver(s): pending named SignPath users and Foundation approval.

All team accounts involved in source control or signing must use multi-factor
authentication. Releases require manual approval and review of their source,
workflow, dependency changes and bundled resources. Apply repository protection
and SignPath build/source restrictions appropriate to the approved team.

Only GitHub-hosted builds of the approved public Folio repository may request
production signatures. Tokens remain in protected GitHub secrets, never source
files. Failed or rejected signing must fail the signed-release job. Unsigned
development artifacts must be explicitly labeled unsigned.

Folio's app, generated uninstaller and final installer must each have a valid,
timestamped Authenticode signature with the approved signer. Microsoft WebView2
and other upstream binaries retain their original signatures. Never change
Windows trust stores or security policies to make a release appear trusted.

## Privacy statement for review

Folio processes document editing, import, export and Hebrew library browsing
locally. Bundled fonts and the DavkaWriter converter do not require a network
download during use. No Folio analytics or document-upload feature is configured.
The Microsoft WebView2 prerequisite has Microsoft's separate update and privacy
behavior, outside Folio's own document processing. Verify this statement against
each release before publishing it on the project's home and download pages.

## Attribution to publish only after acceptance

Free code signing provided by [SignPath.io](https://signpath.io), certificate
by [SignPath Foundation](https://signpath.org).

The Foundation certificate identifies SignPath Foundation as the Windows
publisher. Signing does not guarantee immediate SmartScreen reputation or
acceptance under every organization's application-control policy.
