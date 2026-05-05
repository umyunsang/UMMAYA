# NotoSansKR-Hangul-subset.ttf

Korean Hangul subset of NanumGothic Regular for KOSMOS PDF export (`/export`).

- **Source font**: NanumGothic-Regular.ttf
- **Source license**: SIL Open Font License 1.1 (OFL-1.1)
- **Source URL**: https://github.com/google/fonts/blob/main/ofl/nanumgothic/NanumGothic-Regular.ttf
- **Subset method**: pyftsubset (fontTools) — common Hangul syllables (~6,000 chars covering 99%+ of modern Korean prose) + ASCII + common punctuation
- **Hangul block coverage**: U+AC00..U+D7A3 with rare-final-consonant syllables removed (full coverage of standard prose vocabulary)
- **ASCII coverage**: U+0020..U+007E
- **Punctuation**: U+00A0..U+00FF, U+3000, U+300C-300F, U+2018-2019, U+201C-201D, U+2026, U+2027

## Why bundled

`pdf-lib`'s `StandardFonts.Helvetica` uses WinAnsi 8-bit encoding and cannot represent
Korean characters (PDF export silently fails on Korean text — Audit-7 P0-1).

`pdf-lib` requires a registered fontkit instance to embed any non-standard TTF/OTF font.
The `@pdf-lib/fontkit` package is a peer dependency of `pdf-lib` (already in tui deps from Spec 1635).

## Subset rationale

Full NanumGothic-Regular.ttf is 2.0 MB — exceeds the AGENTS.md "no commit > 1 MB without ask" rule.
Subsetted version is 952 KB. Coverage verified against realistic KOSMOS Korean text including
all standard agency-name vocabulary (도로교통공단, 기상청, 건강보험심사평가원, etc.).

## OFL compliance

OFL-1.1 permits modification + distribution + bundling provided the modified font is also
distributed under OFL. This file inherits OFL-1.1 from the upstream NanumGothic.
