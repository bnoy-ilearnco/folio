# Hebrew-only library — 0.4.3

The 0.4.3 update removes all visible credits, edition/license details and
automatic citations from the library. Passage insertion now adds only the
selected text, with no appended source-credit paragraph or hyperlink. It
preserves RTL formatting, niqqud and cantillation. Original bundled notices
and database provenance remain intact. The 18 unit, 14 browser, 7 production
and 2 Rust checks pass; browser checks assert exact passage text, one inserted
paragraph for a single-paragraph source, zero added links and no credits UI.

The following records the earlier 0.4.2 localization work:

Installed and checked on Windows on 24 October 2026.

All library-facing titles, categories, controls, placeholder text, accessibility
labels, chapter/daf/verse references, search results, empty/error messages,
edition details, license labels and inserted source credits are Hebrew.
The dialog uses Hebrew language and RTL direction, a right-hand sidebar,
and primary-text / Rashi columns ordered from the right. Citation addresses
remain attached to Hebrew-labeled links; no English URL/title is printed into
the document's visible source credit.

The entire 151-entry catalog is checked for localized titles, categories,
edition descriptions and licenses. The original database metadata, source
addresses and raw passages are retained. A full audit of 248,939 passages
found four Latin-bearing source artifacts: three malformed markup fragments,
plus one x-shaped diagram. The presentation/insertion layer removes those
three fragments and renders the diagram as ×. All displayed passages then
contain zero Latin letters. Hebrew text, Aramaic, niqqud and cantillation
otherwise remain intact.

Verification: 18 unit tests, 14 browser interaction tests, 7 production/CSP
tests and 2 Rust corpus/search tests pass (41 total). Coverage includes
Tanakh/Bavli, Rashi, search and empty/error states, local insertion with
source links, reading-position persistence, source/hide vowel modes,
Hebrew-only visible/accessibility labels and RTL sidebar geometry.

Native Windows inspection confirmed Tanakh/Rashi and Bavli/Rashi display,
collection selection, Hebrew daf labels and expanded Hebrew edition/license
details. The current document was saved before the update and reopened with
its dotted border and existing formatting. Native library document text
contains no Latin letters, including the expanded edition details.

The installed database matches the source SHA-256:
`092acacc7280d0daee00aacbf80d6b2dfcfe726a53de90f8f21110bbaa7c5523`.
No runtime service, account or download was added. Signing stays deferred;
0.4.2 is explicitly an unsigned development release.
