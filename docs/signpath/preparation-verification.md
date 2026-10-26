# Folio integration and signing preparation — 26 October 2026

Owner confirmed `bnoy-ilearnco/folio` and MIT licensing for original code and
the integrated offline DavkaWriter converter. Converter branding, Python/runtime
paths, font paths, document metadata and source integrity hashes were updated.
Third-party license texts and font sources remain intact.

Verification on this machine:

- Type checking and Vite production build passed.
- 23 unit checks passed.
- 17 browser checks passed; optional real-document check skipped in that run.
- All 11 production/CSP browser checks passed, including the real Downloads
  worksheet, with the renamed local converter and bundled fonts.
- No former converter branding was found in current source text or built
  frontend files. Superseded integration files are archived under the task's
  `work` directory outside the release source.
- The database remains byte-for-byte unchanged:
  `092acacc7280d0daee00aacbf80d6b2dfcfe726a53de90f8f21110bbaa7c5523`.
- Source publication excludes the corpus, local QA screenshots, generated
  runtime files, build outputs, private documents and signing credentials.

No new installer was built or installed for these preparation changes. The
existing installed app and single offline installer predate this integration
rename and remain unsigned. No SignPath account or signature was activated.
The public repository `bnoy-ilearnco/folio` was created. Foundation application
submission is pending resolution of source-text redistribution and eligibility.
