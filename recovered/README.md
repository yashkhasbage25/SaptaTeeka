# Recovered hand-written text

Markdown recovered from the Next.js attempt that lives on `origin/main`
(commits `97ec785`, `b3141ad`, `5dea025`, Sept–Oct 2025). That branch has a
history unrelated to this one, so the text is copied here to be safe from
whatever happens to the branch.

| file | scope |
|---|---|
| `adhyaya1.md` | chapter 1 up to the Guptavatī on verse 1 — one commentary only |
| `kavacham.md` | a Markdown rendering of `sanitized/kavacham.xml`; same text |
| `keelakam.md` | kīlaka, hand-marked |
| `argala.md`   | argalā, hand-marked |

## Why it is kept

It is hand-corrected, and the pipeline measures around 95% word accuracy, so
for the passages it covers this text is the better reading and should win any
disagreement. It is narrower than the generated XML, not a replacement for it:
`sanitized_auto/adhyaya_1.xml` carries 328 commentary blocks across all seven
ṭīkās where `adhyaya1.md` has one.

## How to use it

Treat it as a correction source, not a build input. Where it overlaps the
generated XML, prefer its readings and fold them into `sanitized/`, which the
build already prefers over `sanitized_auto/`.
