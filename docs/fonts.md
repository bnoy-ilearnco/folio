# Offline document font collection

Folio 0.6.2 adds 13 unmodified open font families, available offline from the Home font picker. Product interface typography is unchanged.

| Style | Hebrew (also includes basic Latin) | English |
|---|---|---|
| Publishing | Cardo, Frank Ruhl Libre, Bellefair | Libre Baskerville |
| Handwriting | Gveret Levin, Playpen Sans Hebrew, Solitreo | Patrick Hand |
| Scroll / manuscript | Keter Aram Tsova, Stam Ashkenaz CLM, Stam Sefarad CLM | Uncial Antiqua, IM FELL English |

Keter follows the medieval Aleppo Codex, Stam fonts follow traditional Torah scroll forms, Uncial Antiqua is manuscript display lettering, and IM FELL English is historical printing. These are stylistic choices applied to ordinary Unicode text.

Use Cardo regular/bold, Frank Ruhl Libre or the existing Noto / Taamey fonts for pointed Hebrew. Keter includes vowels and cantillation but historical positioning may depend on mark order. Stam is unpointed lettering; Solitreo lacks qamats. Decorative/handwriting faces and Cardo italic have incomplete mark coverage; the renderer uses fallback for missing marks. Existing niqqud entry remains available. Single-face families use browser synthetic bold/italic; upstream bold/italic faces and variable weight ranges are provided where available.

Fonts load from local app assets on demand. No font server or system installation is needed. ODT and DOCX retain family names; another word processor needs the corresponding fonts installed to match the appearance. Desktop PDF and print embed/render the local document fonts. The browser preview uses its print dialog for these fonts, avoiding silent PDF font substitution.

Licenses and original font sources are in `public/fonts/collection`; `manifest.json` pins downloaded files to SHA-256 hashes and source URLs. Google Fonts families use OFL 1.1. Culmus families use GPL v2 with the document embedding exception. Candidate Shlomo files were excluded because their embedded noncommercial restriction conflicted with their OFL notice.

## Validation on this Windows machine

26 unit checks and 14 production/CSP browser checks passed; the optional real DWD fixture check was skipped in this run (the other DWD checks passed). All 13 collection faces loaded with external network requests aborted. ODT/DOCX preserved each family name and pointed text. The Chromium PDF check embeds Keter Aram Tsova. Glyph coverage, variable weight ranges and upstream checksum integrity were inspected.

The unsigned 0.6.2 offline installer completed a local update with exit code 0. Native WebView2 displays the grouped choices and font sampler. Library SHA-256 remains `e525e891a7f9de6fed02d227bd31a29c803ef5464aa0a96f04c2f1ded757f438`. Installer SHA-256: `906b54fb527be6d855219a7e750070267ce19bb9c3a86eecf61761351007347a`. Clean-machine installation and every printer driver were not retested.
