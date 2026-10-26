# Product

<!-- impeccable:product-schema 1 -->

## Platform
Desktop: Windows first; Tauri shell with a web-based editor.

## Stack
User selected Tauri with Rust backend and a rich-text editor. ODT is the native format.

## Product Purpose
A simple desktop word processor with advanced text formatting and page layout controls, and few unrelated menu items.

## Capabilities and Constraints
Open and save OpenDocument Text, import/export DOCX, export PDF, print. Preserve formatting within a documented supported subset. No claim of full Microsoft Word compatibility.

## Open Decisions
Product name, commercial distribution, target operating systems beyond Windows, and required compatibility corpus are undecided. Folio is a working name. No paid editing dependencies assumed.

## Hebrew support
User requested Hebrew language support, RTL typing/formatting, and basic Hebrew fonts. Paragraph direction supports automatic, LTR, and RTL. Bundle Hebrew fonts and retain Hebrew language and direction in ODT/DOCX. Native PDF export must use a bidi-capable renderer.
