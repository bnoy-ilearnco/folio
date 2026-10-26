# Mishnayos and Bartenura — Folio 0.6.0

The local offline database now contains:

- Tanakh: 39 component books and 39 Rashi texts, unchanged.
- Babylonian Talmud: 37 Gemara tractates and 36 source Rashi texts, unchanged.
- Mishnah: all 63 tractates, 4,192 mishnayot, in six orders.
- Bartenura: all 63 source commentary books, 21,204 Hebrew comments.

The total is 277 books and 274,335 Hebrew/Aramaic passages. All new books use
the same pinned TorahLM export snapshot as the existing library. Each cached
source is checked against its Git blob hash; parsed Hebrew passage counts must
match each edition's declared count. English translations are excluded.

Choose **משניות**, then a seder and masechta in the sidebar, a perek, and a
mishnah in **בחירת משנה**. Selecting a mishnah highlights it within its chapter;
**כל הפרק** returns to the full-chapter view. Bartenura comments are aligned
beside the corresponding mishnah. Search covers the collection, one tractate,
or all library texts; inserting adds only Hebrew passage text. The reading
position remembers the chapter and selected mishnah. No Rashi is attached to
Mishnah. Pirkei Avot includes the source's sixth chapter, Kinyan Torah; absent
source commentary is not invented or replaced with a different author.

One Latin diagram marker in Bartenura Menachot 6:3:6 is displayed as the curved
symbol ⊂. The raw source remains unchanged in SQLite, as for earlier source
markup/diagram display cleanups. All other vowel marks and source text remain
intact. Tanakh/Bavli books and all 248,939 original passages were compared
record-for-record with the previous database and are unchanged, including IDs.

## Source choice and intended use

The publisher specified free personal/noncommercial library use. Source-edition
license labels and notices are retained internally. No attribution/edition
panel or automatic citation was added to the Hebrew reader. Software MIT
licensing does not relicense source texts or font/runtime dependencies.

HebrewBooks' Shas page was checked in the browser. Its sampled selectable text
was unvowelized. Its terms allow limited free personal/noncommercial copying,
require retained attribution and a copy of the limited license when distributing,
and prohibit automated site access/downloads. The scanned Shas page separately
identifies Moznaim's copyright and permission. No bulk download was attempted
and no claim of unrestricted redistribution was made. The existing vocalized
Bavli was retained following the publisher's personal/noncommercial clarification.

- https://hebrewbooks.org/shas
- https://hebrewbooks.org/media/terms.html

The installed library remains fully offline; these links are development
research references, not runtime dependencies. The database stays out of the
public Git repository. Provider approval and unresolved edition labels remain
separate from local personal use; no signed release is claimed.

## Verification and local installation

Folio 0.6.0 was built and installed successfully on this Windows machine on
26 October 2026. The NSIS update returned exit code 0; the installed executable
reports product/file version 0.6.0. The installed library was opened and showed
the new Mishnayos collection with aligned Bartenura. The app was left open there.
The prior installed app/resources were backed up outside the source tree before
updating. Existing document files were not overwritten.

Checks passed: 23 unit, 19 browser, 13 production/CSP browser (including the
Downloads DWD sample), 3 Rust/database and 3 Python importer tests. The optional
real-document check was skipped in the development browser run and passed in
the production run. Source completeness and unchanged prior records were also
verified independently against the preceding SQLite database.

Native testing selected Mishnah Berakhot 1:5, inspected its aligned commentary,
inserted its Hebrew text into a new document and saved a separate QA ODT outside
the repository. That ODT matches the source mishnah exactly, including niqqud,
Hebrew language and RTL properties, with no added commentary, credits or links.

The final installed build also retained the selected mishnah and its highlight
when hiding and restoring niqqud. The regression check passed in development
and production browser runs. GitHub CI for the source update passed:
https://github.com/bnoy-ilearnco/folio/actions/runs/40370057285.

Installed database SHA-256:
`e525e891a7f9de6fed02d227bd31a29c803ef5464aa0a96f04c2f1ded757f438`.

Installed executable SHA-256:
`5549d4c818a40e6cc2c5905ebaf5b564cfeaf0203124f98b639cf5dc1ab64ec8`.
The unpackaged build differs only in Tauri's three-byte bundle marker (`UNK`
versus the installer's `NSS`); all other bytes match.

Single offline installer: `Folio-0.6.0-Windows-x64-Offline-Setup.exe`,
258,131,169 bytes, SHA-256
`82189c0c832a73d24c7d85e609e79be878487c8d6320e0e41157ec99335ef18a`.
It remains unsigned. Updating this existing machine passed; first installation
on a clean Windows machine and physical printer output were not tested here.
