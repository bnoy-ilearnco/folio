# Folio interface

User chose a familiar Word-like interface. Mode: Operate. Keep the ribbon compact and exclude unrelated office-suite features.

Use a blue application bar, white ribbon, pale neutral document workspace, and white paper. Home / Insert / Layout tabs group real controls. A collapsible inspector exposes paragraph and page details. Preserve familiar shortcuts and selection while using the ribbon. Noto Serif, Noto Sans, and Noto Sans Mono are bundled under the SIL Open Font License for consistent editor and PDF output.

Use Lucide icons at 16–18 px. Labels remain visible on primary file actions and ribbon groups. Focus uses a high-contrast blue outline. Errors and compatibility reports remain visible until dismissed. Typography previews communicate actual document styles.

The editor is a continuous page-width canvas with explicit page breaks. Automatic page composition is performed at output time; do not label its on-screen height or page count as a faithful print preview.

Hebrew support extends the existing ribbon with labeled LTR, RTL, and עברית controls. Direction and language are separate paragraph attributes, with automatic first-strong-character direction. Keep menus and controls in the existing English UI. Document indentation uses logical start edges. Fonts include Noto Sans Hebrew, Noto Serif Hebrew, and David Libre. Windows PDF export uses WebView2 bidi shaping.

The Hebrew library opens from the top bar as a large reference dialog. Its entire interface is Hebrew: titles, categories, navigation, search, messages and passage location labels. It uses lang=he and RTL flow, with the collection/seder/book sidebar on the right and the main text to the right of Rashi. Chapters and daf sides use Hebrew notation. The word processor retains its existing UI language outside the library. When no commentary exists, the text uses the full reading width. Search and insertion are local. The reading UI omits credits and edition details. Insertion adds only the selected passage, with no citation or link. Original provenance and license notices remain in the bundled resources. Remember the last reading position without changing the open document.
