# Folio licensing scope

Folio's original application code and integrated offline DavkaWriter converter
are licensed under the MIT license in `LICENSE`, with the original owner's
authorization dated 26 October 2026. The converter is part of Folio; its source
is in `vendor/folio-dwd` and its bundled source hashes are in
`public/dwd/PROVENANCE.json`.

The MIT license does not relicense the following separately licensed materials:

- Hebrew source texts: `src-tauri/resources/library.sqlite` and
  `LIBRARY-NOTICES.txt`. Edition/license/source metadata is retained per book.
  Redistribution review is pending; see `docs/signpath/license-audit`.
  `tests/fixtures/library.json` includes selected source passages for testing;
  its catalog retains each edition's license and source URL. These source
  texts are not relicensed under Folio's software MIT license. Library use is
  intended to be free and personal/noncommercial.
- Fonts: original per-family license files and Culmus corresponding source
  archives in `public/fonts` and `public/fonts/hebrew`. GPL font exceptions
  and SIL Open Font License terms remain applicable.
- Pyodide: Mozilla Public License 2.0; Python: PSF license. Their notices,
  license texts and source links are in `public/dwd`.
- JavaScript/Rust dependencies: their respective licenses apply. Dependency
  versions are recorded in `pnpm-lock.yaml` and `src-tauri/Cargo.lock`.
- Microsoft WebView2 prerequisite: separately licensed and signed by Microsoft.

This scope notice does not grant redistribution permission for content whose
license is missing, or waive attribution, share-alike, source or other terms.
