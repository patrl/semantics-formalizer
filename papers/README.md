# Paper sources

One directory per paper, named author-year:

```
papers/smith-2019/
  paper.tex        main file: pass this to formalize.py
  ...              anything it \inputs (.tex, .bib, figures)
  EXPECTED.md      optional answer key; never read by the pipeline
```

With the main file called `paper.tex`, the run goes to `runs/smith-2019/`.

Everything here except this file is git-ignored, since most published
papers can't be redistributed. To add an answer key to the repo anyway:
`git add -f papers/smith-2019/EXPECTED.md`.

The pipeline reads a single `.tex` file: `\input`/`\include` aren't
followed yet, so flatten multi-file sources first (e.g. `latexpand`).
