# DavkaWriter import

Use **File → Open** and choose a `.dwd` file. The reader is included in the
desktop application and works without internet access from the first import.
Imported documents save as ODT; DOCX and PDF export use Folio's existing commands.
The original DWD is never overwritten. DWD export is not provided.

Folio includes its own local reader and DOCX converter, integrated under the
MIT license with the original code owner's authorization. A bundled Pyodide
0.29.3 runtime runs it in a disposable worker. It does not contact that website,
a CDN, a conversion service, or a local Python installation. The worker is
terminated after each import and has a two-minute time limit. Imports are
limited to 30 MB, including the converted DOCX, with the existing expanded ZIP
limits. A failed import leaves the current editor document intact.

The import preserves supported Hebrew/English text, niqqud, emphasis, colors,
font sizes, paragraph directions, common tables, PNG/JPEG images and page
settings. Hebrew marks are canonically normalized. Taamey David/Frank, Noto Rashi Hebrew and Heebo substitutes are
bundled. When installed locally, **UniDavka David, UniDavka Rashi and UniDavka Stam**
are used at the original document point sizes. Older Davka font files have a
legacy character map and cannot display Folio's Unicode text directly. Folio
does not copy or distribute the proprietary fonts. Common Windows font names are retained; other fonts use bundled
substitutes with a notice. RTL tables are reordered
into visual order and grid widths are read into editor cell widths.

Folio's editor remains a continuous canvas with one page layout. Imported
pagination, proprietary fonts, multiple sections/columns, floating-object
positions, decorative shapes, vertically merged cells and rich headers/footers
cannot all be represented exactly. Text boxes become document-flow content;
footnote/endnote references and bodies are retained, with bodies appended at
the end instead of the page bottom. Unsupported picture formats and parser
recovery are reported when detected. Review complex imported documents before
printing or relying on their layout. Fixed line spacing, paragraph sizes/indents, table widths/row heights and
cell padding/shading/borders are preserved in ODT and DOCX. Formatted headers
are preserved there too; native PDF/print uses the leading header text style,
with mixed styles and inline boxes simplified in page margin boxes.

Version 0.6.1 retains character-width scaling in ODT/DOCX, with measured tracking
as an approximation in the wrapping editor. Paragraph frames, their padding,
right/center table anchoring, and page-border widths/insets survive save/reopen.
Signed table-border widths and gray percentages were corrected against
DavkaWriter 7's own PDF output: negative border widths still print, and a 91%
gray value produces `#E8E8E8`, rather than the darker stored color swatch.
The import notice lists Hebrew faces still being substituted.

Local QA on 29 October 2026 used the worksheet in Downloads, opened in
DavkaWriter 7 and exported to a separate reference PDF outside the repository.
All 24 unit, 21 development-browser, 14 production/CSP-browser, 3 Rust/database
and 3 Python fidelity checks passed. The original fonts were verified at
18 pt for David and 16 pt for Rashi in the editor. Tests also force the local
fonts unavailable to exercise the portable fallback without external requests.
The native 0.6.1 desktop build opened that same DWD, displayed UniDavka David
at 18 pt in its toolbar, and saved a separate QA ODT. Inspection of that saved
file confirmed UniDavka David at 18/16 pt and UniDavka Rashi at 16 pt. The source
DWD was not changed, and no proprietary font files were added to Folio.
The final NSIS update installed successfully (exit 0), and Windows reports
installed file/product version 0.6.1. Its executable matches the tested build
apart from Tauri's bundle marker; the offline library SHA-256 is unchanged.
The single offline setup is 258,190,869 bytes, SHA-256
`fea608eca46c88c73dbe0c27b43802f140b9a852352987fa0c5f3891d2e6ee76`.
It is unsigned. A clean-machine first install and physical printing were not
tested; the previous installed app and library were backed up before updating.

This is not a pixel-identical layout engine. The reference has 31 pages;
Folio's automatically composed PDF has 37 in this sample. Content extending
beyond text margins can make Chromium shrink the printed document (the sample's
18 pt David became approximately 17.1 pt in the PDF). Headers containing inline
boxes are simplified in PDF/print. The editor and ODT/DOCX keep the original
measurements; review PDF/print layout separately. These limitations are not
hidden by claims of an exact conversion.

The synthetic `tests/fixtures/hebrew.dwd` is reproducible with
`tests/fixtures/make_dwd.py`. Real user samples stay outside the source/release.
Set `FOLIO_DWD_SAMPLE` to a local document to enable the optional worksheet QA.


Noto Rashi Hebrew is also selectable from Home → Font family for new text.
Regular and bold faces are included and work offline with niqqud.
