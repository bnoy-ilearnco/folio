# SignPath Foundation application — draft, not submitted

Project: Folio, Windows desktop word processor, version 0.5.1.

Description: A Tauri/Rust desktop application with a Tiptap editor, Hebrew and
English text entry, right-to-left formatting, manual niqqud, bundled Hebrew and
Rashi fonts, ODT documents, DOCX and DavkaWriter import, PDF/print, page borders,
and an offline Hebrew Tanakh/Babylonian Talmud/Rashi library.

Repository selected by the owner: `https://github.com/bnoy-ilearnco/folio`.
The public repository was created on 26 October 2026. Initial source publication
excludes the bundled text database pending redistribution clearance.

Project license: MIT for Folio's original code and its integrated DavkaWriter
converter, confirmed by the original owner on 26 October 2026.
Third-party fonts, Python/Pyodide, dependencies and source texts retain their
own licenses. A license for Folio cannot grant rights to these materials.

Maintainer/legal organization/contact, public homepage/download URL, named
reviewers and release approvers: to be supplied by the publisher. Do not
invent people, roles or project history. The project is newly prepared for
public release; eligibility and approval remain SignPath's decision.

## Disclosure for Foundation review

The current offline installer contains a 151-book, 248,939-passage database.
Its upstream labels include 35 CC-BY-NC books and 21 books with unknown
licenses. The full inventory is in `license-audit/books.csv`. Exact license
versions and redistribution/attribution obligations need review. Please clarify
Foundation eligibility for this bundled text data; do not treat it as software
covered by Folio's proposed license. The publisher must resolve redistribution
rights before publishing the database or installer.

The installer also includes Microsoft's separately signed offline WebView2
prerequisite. It must keep Microsoft's signature and distribution terms.
Folio does not seek to sign upstream binaries with a Foundation certificate.

## Proposed signing process

Build from reviewed public source on GitHub-hosted Windows runners. Use locked
dependencies, a protected release environment and a manual release approval.
Keep the API token in a GitHub environment secret. Configure SignPath origin
verification and repository/build restrictions. Sign Folio's own app,
NSIS uninstaller and final NSIS installer, then verify their signatures and
timestamps before making the single offline installer available.

The NSIS packaging/signing sequence needs a verified integration before use;
signing the outer installer alone does not sign the installed application.
Do not describe this draft as an operating signing service.

Application: https://signpath.org/apply
Terms: https://signpath.org/terms.html
