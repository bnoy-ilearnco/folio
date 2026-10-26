# Folio

A desktop word processor built with **Tauri + Rust + Tiptap**, with OpenDocument Text (`.odt`) as its native file format. Folio is a working name.

Folio is now built and installed as a Windows desktop application. Launch **Folio** from the Desktop or Start menu. It runs independently of the development server. A standalone executable and Windows installer are included beside the source archive. The browser preview remains available for development.

## Source license and release preparation

Folio's original code, including its offline DavkaWriter converter, is MIT
licensed; see [LICENSE](LICENSE) and [third-party notices](THIRD-PARTY-NOTICES.md).
The repository is being prepared for SignPath Foundation review. No Foundation
signature or acceptance is claimed; current local packages are unsigned.

The bundled Hebrew database is excluded from public source while its edition
rights are reviewed. Local application/library files are preserved. Frontend
builds and tests work without the database. A native build needs a legally
obtained `src-tauri/resources/library.sqlite`; see
[the rights inventory and signing setup](docs/signpath/README.md). The unsigned
desktop CI packaging job is gated until distribution rights for the pinned
corpus are documented; frontend CI remains enabled.

## Installed desktop app

### 0.5.1: import formatting and Rashi font

DWD import now preserves fixed line spacing, paragraph mark sizes, logical
indents and alignment, table widths/row heights, cell padding/shading/borders,
boxed text, rich headers, and compound page borders. These supported properties
survive ODT and DOCX export/import. Exact imported spacing is shown in the
formatting panel; choosing a new line-spacing setting replaces it.

The font menu includes **Noto Rashi Hebrew** (regular/bold), Taamey David CLM,
Taamey Frank CLM and Heebo, bundled for offline use. Common Windows font names
are retained instead of being collapsed into Noto Serif. Davka Rashi imports
use Noto Rashi Hebrew. Native PDF embeds the bundled Rashi font. Font licenses
and the Culmus source archives are distributed with the fonts.

Reopen the original DWD to use the improved importer. ODT copies made by the
older importer cannot reconstruct formatting already flattened by that version.
Folio still uses a continuous canvas and one page layout, so pagination and
complex object placement can differ from Folio. PDF/print repeats header text
using its leading font/size/emphasis; mixed header styles and inline boxes are
simplified in Chromium margin boxes. Full header formatting is kept in ODT/DOCX.

The font and formatting improvements are installed and verified. Windows
Application Control blocked the final rebuilt installer containing additional
PDF header/page-number fixes. Those final fixes are built/tested but not
installed. See the release manifest and native verification for build hashes.

### Previous 0.5.0: DavkaWriter import

Open `.dwd` files with **File → Open**. The bundled Folio reader works fully
offline, including on the first import, with no system Python dependency.
Hebrew/English text, niqqud, common styles, RTL tables and supported images
flow into Folio. Save as ODT or export DOCX/PDF; the source DWD stays unchanged.
Complex layouts and unavailable fonts may change. Notes are retained at the
end of the document. See [DWD import details](docs/davkawriter-import.md).

50 automated checks pass. Native testing opened the Downloads worksheet and
verified all 538 nonempty paragraphs and five tables in a separately saved ODT.

### Previous 0.4.4: Insert tab

Removed the Link button and its link-edit dialog from the Insert tab.
Type checking, the release build and four editor smoke tests pass.

### Previous 0.4.3: simplified library

The library no longer displays credits, edition descriptions or license details.
Its **הוספה למסמך** action inserts only the selected passage, retaining Hebrew,
RTL paragraph formatting, vowels and cantillation. No citation paragraph,
source-credit text or source link is appended. Book/chapter/daf navigation and
passage location labels remain available for finding texts. Bundled license
notices and original provenance are retained in the application resources.
All 41 automated checks pass, including exact passage-only insertion and
absence of credits/edition controls in the development and production builds.

### Previous 0.4.2: Hebrew-only library

The library is Hebrew throughout: book names, categories, menus, search,
status/error messages, editions, license labels, and inserted citations. Its
layout flows right to left, with the sidebar on the right and the main text to
the right of Rashi. Chapter, verse, daf and commentary references use Hebrew
notation. Source addresses remain attached to Hebrew-labeled citation links.

Original corpus text and provenance remain in the database. The display and
insertion layer cleans three known stray source-markup fragments and renders
one cross-shaped diagram as ×. An audit of all 248,939 passages confirms no
Latin letters remain in displayed passages after those four adjustments.
All 151 catalog entries have Hebrew titles, category labels, editions and
license labels. Automated checks: 18 unit, 14 browser, 7 production/CSP and
2 Rust tests. Signing remains deferred. The current packages are
`Folio-0.4.2-Unsigned-Setup.exe` and `Folio-0.4.2-Unsigned-Portable.zip`.

### Previous 0.4.1 development update: Hebrew vowels and page borders

Installed and tested on this Windows computer on 24 October 2026. Signing is
deferred at the publisher's request until development and testing are complete.
The publisher will choose a signing provider later; Azure is not the selected
plan. The installed app and versioned packages remain **unsigned**.

Native QA covered manual vowel entry/removal/Undo, Hebrew/English switching,
source-vowel reading and hide controls, cited source insertion, all border
presets, ODT/DOCX export/import and two-page native PDF export. Physical print
output remains unverified: Windows waited for a printer connection and the
operation was canceled. No printer or Windows security settings were changed.

QA found and fixed an extra blank paragraph on DOCX page-break round-trip.
The installed 0.4.1 export/import now preserves paragraph structure, all 18
Hebrew marks, cantillation, citations and the double border in the test file.
See [native verification](docs/native-verification.md) for the scope and limits.

- **Home → Vowel keyboard:** all 18 niqqud controls, including reduced vowels,
  qamats qatan, holam haser, dagesh/shuruk, shin/sin dots, meteg and rafe. Place
  the cursor after a Hebrew letter or select it. Changing a vowel replaces the
  existing vowel rather than stacking conflicting points; clear removes vowel
  marks while retaining cantillation.
- **Home → Remove niqqud:** remove vowel marks from selected text or the current
  paragraph, preserving consonants, cantillation and rich formatting. Undo is
  independent of typing.
- **Library → Vowels:** show source-edition vowels or hide vowel marks for reading.
  Insertion always retains source vowels. Unpointed editions remain unpointed.
  Manual vowel entry and reading work completely offline.
- **Layout → Page borders:** None, Single, Double, Dashed, Dotted, Bold, with a
  color selector. Borders round-trip in ODT/DOCX and repeat on every composed
  PDF/printed page. Editing remains a continuous canvas. Explicit page breaks
  place the caret in the following paragraph, ready to continue writing.

The new build passed 15 unit tests, 12 browser tests, 2 production/CSP checks,
and the existing Rust database tests.
The border ODT example validates against the official ODF 1.3 schemas. Both
pages of the browser-composed border PDF were rendered and inspected.

For a signed build after configuring a publisher identity:

```powershell
./scripts/build-signed.ps1
```

The signing workflow checks trusted Authenticode signatures and timestamps on
both the application and installer. It has no self-signed or unsigned fallback.

Installed on this computer at `C:\Users\Admin\AppData\Local\Programs\Folio\folio-desktop.exe`, with Desktop and Start menu shortcuts. The current development installer is `Folio-0.4.1-Unsigned-Setup.exe`. Unversioned `Folio-Setup.exe` and `Folio.exe` are earlier 0.3.0 artifacts. For the current portable package use `Folio-0.4.1-Unsigned-Portable.zip`; keep the accompanying `resources/` folder beside it for the offline library. End users do not need Rust, Node.js, or the C++ build tools. WebView2 is the runtime used by the app; the installer checks for it.

The missing development dependencies were installed: Rust/Cargo 1.99.1 with the MSVC toolchain, rustfmt, Visual Studio Build Tools 2022 with C++ tools, and Windows SDK 10.0.26100.0. WebView2 was already installed.

Native smoke checks passed for launch, document editing, ODT save and overwrite, DOCX open/import, and PDF export with searchable text. The print dialog opened and was canceled; the configured printer was unavailable, so no physical print job was tested. See `docs/native-verification.md`.

## Build or develop

Install Node.js 24 and pnpm 11, then run from this folder:

```powershell
pnpm install --frozen-lockfile
pnpm dev
```

Open <http://127.0.0.1:1420>. The preview uses file uploads and downloads. Document editing and conversion work locally; no conversion server or account is required.

The source archive also includes the verified production build in `dist/`. With Node.js installed, double-click `Browser preview.cmd` or run `node scripts/preview.mjs` and open <http://127.0.0.1:1440>. This preview does not require installing project dependencies.

For the desktop application, install the [Tauri Windows prerequisites](https://v2.tauri.app/start/prerequisites/): Rust with the MSVC toolchain, Microsoft C++ Build Tools with the Windows SDK, and WebView2. Then run:

```powershell
pnpm desktop
```

Build a Windows installer:

```powershell
pnpm tauri build
```

The installer will be written under `src-tauri/target/release/bundle/nsis/`. The included GitHub Actions workflow can build it on a Windows runner once this folder is used as a repository root. That workflow has not been run here. The desktop configuration currently targets Windows; other operating systems need their own packaging and native QA.

## Offline Hebrew library (0.3.0)

Local installation note: the library reader was installed successfully, and its
database was updated to the final Tanakh/Bavli collection. Windows Application
Control blocked the final unsigned installer under its signing policy. The
already installed reader works with the final data but retains an empty
Yerushalmi menu entry. The included final installer and portable package remove
that entry; installing that executable update requires trusted signing or
administrator approval under the computer's policy. No security settings were
changed or bypassed.

Click **Hebrew library** in the top bar. Its local SQLite database contains **151 texts and 248,939 Hebrew/Aramaic passages**, downloaded from the official [TorahLM repository](https://github.com/TorahApp/TorahLM-download), snapshot `0b913ff6b83ed3ca4f4728c16b88662a74d2856e`:

- Tanakh: all 39 component books, organized as Torah, Neviim, Ketuvim, with 39 Rashi texts. These components comprise the traditional 24-book canon.
- Talmud Bavli: 37 extant Gemara tractates, ordered by seder, plus 36 Rashi texts available in the source. Rashi does not cover every passage; no alternative author is relabeled Rashi. This source supplies no Rashi on Tamid.
The Jerusalem Talmud is excluded, as requested. Shekalim has Yerushalmi Gemara and is excluded from this Babylonian-only collection.

Browse by chapter or daf/amud, read Hebrew beside aligned Rashi, and use **Insert with source** to insert a passage at the saved cursor position. Citations retain the title, reference, edition, license label and source URL. Search can cover a book, collection, or the whole library, and ignores vowels/cantillation and final-letter differences. Search uses AND across words with word-prefix matching, returns 50 results per page, and includes Rashi. The last reading location is remembered on this computer. No AI-generated text is included.

**The installed reader makes no network requests.** Database, full-text index, and Hebrew fonts are installed together. No account, API key, live TorahLM connection, or development server is needed. The browser preview directs users to the desktop app for the library.

All 151 book imports match TorahLM's declared Hebrew segment counts. Genesis etc. retain niqqud/te'amim; Markdown emphasis is converted to plain text. Joshua 21:36–37 retain the source edition's dash placeholders. Source catalog names/traditional commentary attributions are retained. This verifies the source snapshot's coverage, not a critical edition's textual accuracy.

Per-book edition and license metadata are accessible under **Edition, licenses & coverage** and in `docs/library-manifest.json`. TorahLM's upstream source is Sefaria. The data has mixed license terms: public domain/CC0, attribution/share-alike, noncommercial, and some unspecified labels. Unspecified fields remain marked unspecified; software licensing does not grant redistribution rights to the texts. English translations are excluded. Full notices are bundled in `src-tauri/resources/LIBRARY-NOTICES.txt`.

The database is bundled in the installer (about 101 MB uncompressed). To rebuild it from the pinned source, with Python 3 installed:

```powershell
python scripts/build_library.py --cache ../../work/torahlm-cache
```

The builder verifies each cached download against the pinned Git blob hash, validates declared passage counts, builds a separate normalized FTS5 index, checks SQLite integrity, and replaces the previous database only on success. To deliberately use a new source snapshot, add `--commit main`; review the resulting manifest before distributing an update. Runtime library commands open the database read-only on a worker thread. The source package includes the complete built database, so builds do not download the corpus again.

## Hebrew and right-to-left writing (0.2.0)

Click **English** to switch back to English, LTR, and Noto Serif. Click **עברית** on Home to set the current paragraph to Hebrew, right-to-left direction, and Noto Sans Hebrew. Use **RTL / LTR**, the **Paragraph direction** selector, or **Ctrl+Alt+R / Ctrl+Alt+L** to change direction. Automatic mode follows the first strong character in each paragraph. New paragraphs inherit the selected language and direction. Language changes apply to the document text; menus remain in English.

Bundled Hebrew fonts: **Noto Sans Hebrew**, **Noto Serif Hebrew**, and **David Libre**, in regular and bold. The fonts work offline inside Folio; they are not installed globally into Windows. Font fallback also allows Hebrew when the ordinary Noto text fonts are selected. Hebrew vowel marks, mixed English, numbers, paragraph alignment, logical start indentation, and RTL list markers are supported. A Hebrew keyboard layout is still selected through Windows, or text can be pasted normally.

ODT and DOCX export retain paragraph direction and Hebrew language/font metadata. Automatic direction is resolved to its effective direction when written to those formats. Files opened in another application use that application's font availability. Full interoperability with every Word/LibreOffice layout is not implied.

**Windows desktop PDF export now uses WebView2's print engine**, with the same browser bidi shaping as the editor, rather than reversing text or relying on the previous PDF renderer. It preserves mixed-language ordering and embeds rendered fonts. The browser preview opens the print dialog for Hebrew PDF export; choose Save as PDF. Non-Hebrew preview PDF exports retain the existing PDF renderer.

Hebrew checks: ten format tests and six browser tests pass, including Hebrew/English ordering, explicit and automatic direction, inherited language/direction after Enter, ODT round-trip, DOCX bidi XML, lists, and rendered print output. The Hebrew ODT sample passes the OASIS ODF 1.3 schemas. Native Windows PDF export was tested with Hebrew vowel marks, English, dates, and numbers; generated pages were rendered and inspected.

## Included

- Home, Insert, and Layout ribbon tabs, with an optional formatting panel.
- Font family, size, bold, italic, underline, strike, text color, highlighting, subscript, and superscript.
- Paragraph styles, alignment, line spacing, spacing before/after, indentation, hanging indents, and keep-with-next.
- Bulleted and numbered lists; basic tables with row/column insertion, deletion, and merging; PNG/JPEG images; hyperlinks.
- A4 and Letter paper, portrait/landscape orientation, margin presets and custom margins, explicit page breaks.
- Plain-text headers and footers, and generated page numbers in document exports.
- ODT open/save, DOCX import/export, direct PDF export, and system printing.
- Undo/redo, literal find/replace, word/character counts, zoom, unsaved-change prompts, and a local recovery copy.

Opening a document always requires choosing a destination on its first ODT save. This protects the original file when a conversion simplifies unsupported content. Subsequent desktop saves reuse the chosen destination and replace it atomically. Browser saves create downloads.

## Format compatibility

| Feature | ODT | DOCX | PDF |
| --- | --- | --- | --- |
| Common rich text and paragraph formatting | Read/write | Read/write | Export |
| Headings and basic lists | Read/write | Read/write | Export |
| Tables and embedded PNG/JPEG | Read/write | Read/write | Export |
| Paper, margins, orientation | One document layout | One document layout | One document layout |
| Plain headers, footers, page numbers | Read/write | Common fields | Generated on export |
| Multiple section layouts, columns, floating objects | Simplified/unsupported | Simplified/unsupported | Unsupported |
| Notes, comments, tracked changes, generated indexes | Unsupported | Unsupported | Unsupported |

This is a defined subset of ODF 1.3 and DOCX, not full Word or LibreOffice compatibility. Import warnings identify many unsupported structures, but do not guarantee detection of every fidelity loss. Font themes, paragraph/run borders, advanced list numbering, tab stops, positioned objects, and complex field codes are not fully mapped. DOCX nested lists are flattened on import. DOCX vertical cell merges are simplified on import. ODT repeated rows/cells and deeply complex external styles need further interoperability work.

The editor is a **continuous canvas at the chosen paper width**, with markers for explicit page breaks. It does not display automatic page boundaries. Desktop PDF export composes output pages with the Windows browser engine. It uses bundled or installed fonts and browser font fallback. The browser preview PDF renderer for non-Hebrew documents uses the original three Noto fonts; Hebrew preview PDFs use browser printing. DOCX/ODT reference font names; their appearance in another application depends on installed fonts.

Direct print sends the document body to the operating system's print dialog. For repeating headers/footers, generated page numbers, and the PDF layout, **export PDF and print that PDF**. Direct-print paper settings can also depend on the printer driver.

Files are limited to 30 MB on open, 2,000 ZIP entries, and 100 MB expanded content. Individual inserted images are limited to 5 MB. Recovery uses local webview storage, which can run out of space for image-heavy documents; recovery failures are displayed. Save important work to a file.

## Verification

```powershell
pnpm test
pnpm build
# With pnpm dev running in a second terminal, and Microsoft Edge installed:
pnpm test:browser
```

Verified in this environment:

- TypeScript check and Vite production build.
- Ten format tests covering ODT packaging, content/styles/layout round-trips, merged tables, ordered list starts, embedded images, malformed input, XML entity rejection, DOCX conversion, and PDF layout definitions.
- Six browser tests covering typing/formatting, save/reopen, DOCX import, PDF download, literal replacement, recovery, unsaved-change cancellation, and preservation of existing work on a failed import.
- Both example ODT packages pass the official OASIS ODF 1.3 Relax NG schemas for content, styles, metadata, and manifest.
- Exported example PDF contains two pages with searchable text and generated page numbers.
- Interface inspected at 1440×1000 and 1000×760.

Optional ODT schema validation requires Python and lxml. Download the [official OASIS schemas](https://docs.oasis-open.org/office/OpenDocument/v1.3/os/schemas/), save `OpenDocument-v1.3-schema.rng` as `odf.rng` and `OpenDocument-v1.3-manifest-schema.rng` as `manifest.rng`, then run:

```powershell
python scripts/validate_odt.py examples/advanced.odt --schemas path/to/schemas
```

## Project structure

`src/main.ts` owns the ribbon, editor, and document lifecycle. `src/model.ts` defines the document and page settings. `src/formats/` contains local ODT, DOCX, and PDF adapters. `src-tauri/src/main.rs` owns native dialogs, authorized save destinations, atomic file replacement, and printing. `public/fonts/` contains the bundled Noto fonts and their license.

Before a public release, broaden Windows native QA beyond the smoke checks, test a corpus of real Word/LibreOffice files, add automatic pagination if required, extend the compatibility matrix, and decide signing, licensing, and distribution. No code-signing or release publishing has been performed.

Version 0.2.1 adds paired English and Hebrew writing buttons, including active language feedback and matching language-selector behavior.


## Share one installer

Share `Folio-0.5.1-Windows-x64-Offline-Setup.exe` alone (254,792,814 bytes).
It contains the application, offline library, bundled Hebrew/Rashi fonts,
DWD reader/Python runtime, license resources and Microsoft's offline WebView2
prerequisite installer. No portable ZIP or source folder is required.

The Folio installer remains unsigned. Windows may warn about or block it;
the prior rebuilt unsigned installer was blocked by Application Control on
the development computer. This offline package was built and its inputs
verified, but a fresh-machine installation has not been performed. Signing
remains a separate step before a trusted public release.

To reproduce after building: `pnpm tauri bundle --bundles nsis`, then
`node scripts/package-offline-installer.mjs`. The installer SHA-256 and
packaging manifest are saved beside the EXE. The embedded Microsoft runtime
was verified as Microsoft-signed before bundling.
