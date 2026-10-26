# Windows desktop verification

Verified on October 23, 2026.

## Installed dependencies

- Rust and Cargo 1.99.1, stable `x86_64-pc-windows-msvc` toolchain.
- rustfmt.
- Visual Studio Build Tools 2022 17.14.42 with the C++ build workload.
- MSVC 14.44.35207 and Windows SDK 10.0.26100.0.
- Existing WebView2 155.0.4283.62.
- NSIS downloaded and hash-verified by the Tauri CLI during bundling.

The Microsoft Build Tools installer signature was verified before execution. Both prerequisite installation and the Folio installer completed with exit code 0.

## Build and install

`tauri build` completed in release mode and produced a Windows x64 executable and NSIS installer. `Cargo.lock` now records the resolved Rust dependencies. The app was installed in `C:\Users\Admin\AppData\Local\Programs\Folio`, with Desktop and Start menu shortcuts.

## Native smoke checks

- Launched the installed executable in its own desktop window, using the bundled `http://tauri.localhost/` origin.
- Typed a document and saved an ODT through the native Windows save dialog.
- Added more text and saved again to the same file. Inspected the ZIP/XML on disk to confirm the additional text persisted.
- Exported a PDF through the native save dialog. Verified its PDF signature, one-page structure, and searchable text, including the additional saved text.
- Opened the example DOCX through the native Windows open dialog. Verified imported heading, body text, lists, table, and compatibility warning.
- Opened the WebView2 print interface. The configured printer connection was unavailable; canceled that connection and inspected the print controls, then canceled without sending a job. Physical printing remains untested.
- Returned the application to a new blank document.

The prior seven format tests and four browser tests also passed. No editing or conversion code changed during this native build. Added Vite's standard exclusion for `src-tauri` so development file watching does not traverse Rust build artifacts.

The executable is an unsigned development release. Existing document compatibility and continuous-canvas limitations still apply; see the README.

## Hebrew update, version 0.2.0

Rebuilt and upgraded the installed application successfully. Verified the Hebrew ribbon button selects Hebrew language, RTL direction, and Noto Sans Hebrew. Typed Hebrew with niqqud, English, numbers, parentheses, and a date. Exported through the new native WebView2 PrintToPdf command. Confirmed A4 output, searchable Hebrew and Latin text, preserved numbers, and inspected the rendered PDF. Ten format tests, six browser tests, TypeScript, Rust cargo check, release compilation, and Hebrew ODT schema validation passed. The update did not install fonts globally or change Windows keyboard settings.

## Offline library, version 0.3.0

Built and installed the initial Windows NSIS package containing the local library.
After the user selected Bavli only, rebuilt the corpus and a final installer.
Windows Application Control blocked execution of that final unsigned installer
(Code Integrity events 3033/3077: Enterprise signing level requirements).
No security settings were changed or bypassed. Updated only the existing
installation's SQLite data and notices, then reopened its already installed
executable successfully. The final packaged UI has only Tanakh and Bavli;
the installed executable retains an empty Yerushalmi selector entry until a
trusted signed/approved executable update can be installed.
The installed SQLite resource's SHA-256 matches the verified source database:
`092acacc7280d0daee00aacbf80d6b2dfcfe726a53de90f8f21110bbaa7c5523`.
The existing blank English-format document was saved before the update.

Native checks on the installed `http://tauri.localhost/` application:

- Opened Genesis chapter 1: 31 base passages and 55 aligned Rashi comments, with niqqud and cantillation rendered by bundled fonts.
- Searched unpointed Hebrew `בראשית ברא`: found the pointed Genesis passage and Rashi passages through the local index, with paginated results.
- Confirmed the final database is scoped to Tanakh and Bavli only, per user preference; Yerushalmi texts are excluded. The packaged UI has two collection options; the installed executable still exposes its now-empty older third option.
- Switched to Bavli Berakhot 2a: 14 passages and 17 aligned Rashi comments, with daf/amud navigation and seder-organized tractates.
- Inspected the corrected Hebrew-only Rashi output after a regression test caught translations that start with Hebrew quotations.

Verification: 10 existing format tests, 9 browser tests, 2 Rust database/search tests,
and 3 Python importer tests pass (24 total). Browser library tests use recorded
IPC fixtures for interaction checks; Rust tests query the full bundled database.
All 151 imported texts match the source's declared Hebrew passage counts;
SQLite integrity succeeds; all Rashi base references match existing passages.
An audit found no passages with substantial Latin translation text in the final
database. No source texts, fonts, or search results are fetched at runtime.

The coverage manifest records editions, source-file hashes, licenses, and the
pinned TorahLM commit. Completeness is relative to that source snapshot; Rashi
coverage varies, as stated in the UI and README. No physical printing changes
were made or retested in this update.

## Installed 0.4.1 update: native QA on 24 October 2026

The Windows NSIS installer completed successfully and the installed executable
reports version 0.4.1. It launched from the installed application directory.
The initial app contained an empty document; the prior executable was backed
up before updating. The final QA document is saved separately under
`outputs/desktop-qa-0.4.0/` (the folder includes the baseline 0.4.0 tests).

Verified in the installed Windows application:

- Hebrew shortcut selects the bundled Hebrew font, language and RTL; English
  restores English/LTR. Enter inherits paragraph direction.
- Manual shin dot and qamats insertion, replacement with patah, clearing,
  isolated Undo, paragraph niqqud removal and restoration. Cantillation remains.
- All eighteen Hebrew marks can be displayed, saved and round-tripped.
- Source vowels in actual Tanakh/Rashi passages; hiding/restoring vowels; cited
  insertion while marks are hidden retains the original pointed source text.
- None, Single, Double, Dashed, Dotted and Bold border settings.
- Native ODT save/reopen, DOCX export/import, and conversion back to ODT.
- Native WebView2 PDF export creates two pages, puts the second-page marker
  on page two, repeats the double border, and renders Hebrew and English.
  Both pages were rendered with Poppler and visually inspected.

Native QA exposed an additional empty paragraph after DOCX page-break import.
0.4.1 gives Folio's structural break carrier a dedicated style and recognizes
it on import without treating it as a blank paragraph. Ordinary empty Word
paragraphs are retained. A regression test covers both cases. A second native
export/import cycle verified exact paragraph-text equality between source ODT
and converted ODT, border equality, all 18 marks, cantillation and citation.

Final automated checks: 15 unit tests, 12 browser interactions, 2 production/CSP
checks and 2 Rust corpus/search tests passed. The ODT test artifact passes the
official ODF 1.3 schemas. The bundled SQLite SHA-256 remains
`092acacc7280d0daee00aacbf80d6b2dfcfe726a53de90f8f21110bbaa7c5523`.
No source texts or fonts are downloaded by the installed reader at runtime.

Limits: the Print command opened Windows' printing flow, which waited for a
printer connection. It was canceled before sending a job; print-preview and
physical output for this build are not confirmed. Border color persistence is
covered by automated export/import and PDF checks; the native color popup was
opened and its keyboard adjustment/cancel behavior inspected. Network adapters,
printer configuration and Windows security settings were left unchanged.

Signing is deferred by the publisher until the program is complete and tested.
The publisher has no Entra/Azure account and will select another plan later.
No account or paid service was created. All current artifacts are unsigned;
the signing helper remains optional and was not used for these builds.

## Installed 0.4.2: Hebrew-only library

See [Hebrew library verification](hebrew-library.md) for the complete language audit, native Windows inspection and 41 passing automated checks. The corpus database is unchanged. Signing remains deferred.


## Installed 0.4.3: passage-only library insertion

Removed visible library credits and edition/license details. Insertion adds only the selected passage, with Hebrew RTL formatting and source vowels; no attribution paragraph or hyperlink is appended. All 41 automated checks pass. Native Windows inspection confirms the credits section is absent and the insertion controls read הוספה למסמך. The previous open document was saved and reopened with its formatting intact. Bundled notices and original source data remain in the package.



## 0.5.0 — DavkaWriter import (26 October 2026)

Installed the unsigned 0.5.0 NSIS build (installer exit 0; installed file/product
version 0.5.0). Preserved the prior recovery document in a separate ODT backup
before testing. Opened the user's 113,807-byte DavkaWriter 550 worksheet from
Downloads through the native Open dialog, using the embedded local Folio and
Pyodide assets. Hebrew niqqud, emphasis, page settings and RTL tables displayed.

Saved a separate ODT test copy; the DWD was not overwritten. An XML comparison
against the unmodified Folio converter's DOCX confirms all 538 nonempty
paragraphs match after canonical Unicode/whitespace normalization. The saved
ODT contains five tables, 3,867 Hebrew letters and 2,688 Hebrew marks. Visual
QA confirmed correct RTL column order. Fonts are substituted and worksheet
pagination/spacing can differ, as the import notice explains.

Automated checks: 21 unit tests, 17 browser tests, 10 production/CSP tests and
2 Rust tests pass (50 checks). An additional real-sample paragraph comparison
passes. The production offline test blocks all nonlocal requests and verifies
no external requests, including on first engine load. Damaged-file rejection
preserves current work and permits a subsequent valid import. A synthetic
fixture verifies Hebrew/English styles and ODT round-trip.

No physical printing was performed for this change. Signing remains deferred.


## 0.5.1 — import layout and Rashi typeface (26 October 2026)

Installed the first 0.5.1 build successfully and verified it in native Folio.
The open document was preserved before updating. Reimported the original DWD
worksheet: the header retains its size, centered alignment and box; the double
page border, cell shading, individual border patterns, narrow padding and
fixed line spacing are now visible. The formatting panel identifies exact
spacing rather than displaying it as an approximate multiplier.

A separately saved native ODT retains all 538 nonempty body paragraphs and
five tables. Noto Rashi Hebrew, Taamey David CLM, Taamey Frank CLM and Heebo are
bundled. Native PDF verification confirmed an embedded NotoRashiHebrew-Regular
font stream; rendered Rashi text and niqqud were visually checked. The PDF is
39 pages; the Folio reference is 37, so exact pagination parity is not claimed.

The final rebuild additionally fixes duplicated cached PAGE-field text in the
footer and carries the leading rich-header text style into PDF margin boxes.
It passes 23 unit, 18 browser and 11 production/CSP checks (52 total), including
Rashi regular/bold offline selection, ODT/DOCX round-trips, exact spacing, table
metrics and rich-header preservation. However Windows Application Control
blocked that final installer at execution. No security settings were changed
and no alternate installation bypass was attempted. The installed earlier
0.5.1 build includes the requested font and import improvements; those last
PDF header/page-number fixes remain uninstalled. Release metadata records
this distinction with the installed and packaged executable hashes.
