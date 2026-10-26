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
bundled. Common Windows font names are retained; other fonts use bundled
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

The synthetic `tests/fixtures/hebrew.dwd` is reproducible with
`tests/fixtures/make_dwd.py`. Real user samples stay outside the source/release.
Set `FOLIO_DWD_SAMPLE` to a local document to enable the optional worksheet QA.


Noto Rashi Hebrew is also selectable from Home → Font family for new text.
Regular and bold faces are included and work offline with niqqud.
