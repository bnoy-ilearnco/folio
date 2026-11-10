# Mekorot-Rashi Folio 1.004

LPPL 1.3c derivative maintained by the Folio project. The original font authors are not responsible for this derivative or its support. The original unmodified Mekorot-Rashi.ttf, original FontForge source and LPPL license remain in this directory. Original download URLs and SHA-256 hashes remain in the parent manifest.

Changes from Mekorot-Rashi 0.003:
- Extend mark-to-base coverage for hataf vowels and rafe to all Hebrew base letters.
- Center composite vowels using the existing per-letter vowel anchors.
- Give below-base vowels clearance on descending non-final letter forms.
- Raise and center rafe clear of letter ink, holam and shin dots.
- Add a zero-advance meteg glyph with base and mark-to-mark anchors; a mark filtering set skips intervening dagesh/shin dots so meteg attaches beside the vowel.
- Correct holam-haser's GDEF classification and add its missing anchors.
- Add subsequent-mark anchors to the vav-holam GSUB form.
- Increase ascent metrics to include raised marks.
- Rename family/full/PostScript/unique IDs and identify this derivative in font metadata.

All original glyph outlines and advance widths, the original GSUB table, and final-kaf/furtive-patah contextual rules are preserved. No cantillation glyphs are added. Single-face bold/italic are still synthetic.

Rebuild: install scripts/requirements-fonts.txt, run scripts/build-mekorot-font.py, then scripts/test_mekorot_font.py. The Python build script is the complete editable source of these changes on top of the included upstream TTF. FontForge SFD is the unmodified upstream source, not a source of the repaired binary by itself.
