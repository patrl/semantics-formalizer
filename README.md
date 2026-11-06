# semantics-formalizer
A procedure for auto-formalizing a semantics paper in Lean.

Give it the LaTeX source of a formal-semantics paper. It extracts the
paper's definitions, examples and claims; formalizes the definitions in
Lean 4; states each claim in Lean for you to review; and then proves or
refutes each statement. A refutation is a Lean proof of the negation,
usually a countermodel. Every proof is checked by Lean and audited
against cheating (`sorry`, extra axioms, smuggled definitions).

See [SPEC.md](SPEC.md) for the full design and [TODO.org](TODO.org) for
progress.

> **Early prototype.** Tested only on the two toy papers in `examples/`,
> never yet on a published paper. Core Lean only (no Mathlib), so papers
> that need sets, cardinality or lattice theory will hit limits.

> **Tested only with Claude.** The design is agent- and model-agnostic (see
> SPEC.md §4, "Agent and model independence"), but the pipeline has only
> been run with Claude: model calls go through `claude -p`, and the project
> is developed in Claude Code. Other agents or models may work, but are
> unsupported until they pass the acceptance suite.

## Requirements

- Python 3.10 or later (standard library only).
- [Lean 4](https://lean-lang.org/) with `lean` on your `PATH`. Tested with
  Lean 4.35.0; no Mathlib needed.
- The [Claude Code](https://claude.com/claude-code) CLI, `claude`, logged
  in. Each model call runs `claude -p` in an empty temporary directory, with
  no tools, settings, MCP servers or project memory, so the model sees only
  the prompt.

Cost: a run on one of the toy papers costs about $3–5 in model usage
(back-translation is about $0.10 per claim).

## Quickstart

The paper must be a single self-contained `.tex` file (no `\input`, and
author macros are not yet expanded).

```sh
python3 formalize.py extract mypaper.tex   # 1. definitions, examples, claims
python3 formalize.py defs    mypaper.tex   # 2. definitions in Lean
python3 formalize.py state   mypaper.tex   # 3. each claim as a Lean statement
python3 formalize.py backtranslate mypaper.tex  # 3b. blind check of each statement
#    review runs/mypaper/statements.json here (see below)
python3 formalize.py prove   mypaper.tex   # 4. prove or refute each statement
```

`state`, `backtranslate` and `prove` take an optional claim id to do one claim only, e.g.
`python3 formalize.py prove mypaper.tex prop3`.

Outputs go to `runs/<paper name>/`: the file's name, or its folder's name
if the file is called `paper.tex`, `main.tex` and so on. Use `--out DIR`
for another location. A run directory remembers which paper it belongs to
and refuses to be reused for a different one.

To try it on a toy paper with a known answer key:

```sh
python3 formalize.py extract examples/toy-fol/paper.tex
# ... and so on; compare with examples/toy-fol/EXPECTED.md
```

## What to check after each step

Each step builds on the previous one, so check its output before going on.
There is no automatic check that later outputs are up to date: if you edit
an earlier output, rerun the steps after it.

1. **`extract` → `claims.json`.** One entry per definition, example and
   claim, in order. Check that nothing is missing and that each `statement`
   says what the paper says. The `concerns` field is where the model notes
   doubts, including claims it thinks are false. `source` gives the item's
   lines in the paper.
2. **`defs` → `Defs.lean`, `Defs.notes.md`.** The paper's definitions as a
   Lean file, wrapped in a namespace named after the paper. The notes list
   every interpretive choice the model made. If you disagree, edit
   `Defs.lean` by hand (it must still compile).
3. **`state` → `statements.json`.** Each claim as a Lean proposition,
   stated on top of `Defs.lean`, with the model's notes on how it read the
   claim. **This is the important review:** the prover proves or refutes
   each statement exactly as written, so a statement that doesn't match the
   paper gives a meaningless result. Edit a `statement` to fix it, or
   delete an entry to skip that claim.

   **`backtranslate` → `backtranslations.json`** helps with this review
   without reading Lean. For each statement, a model that sees only the
   Lean (comments, docstrings, claim ids and the paper all withheld) says
   in English what it says, both in the formalization's terms
   (`surface`) and with the definitions expanded down to truth conditions
   (`unfolded`). A second model compares that with the paper and lists the
   differences:
   - `substantive`: the truth conditions differ (the item is `flagged`);
     look at these first;
   - `choice`: the paper is ambiguous and the statement takes one
     reading; check it's the one you want;
   - `wording`: same truth conditions, different phrasing.

   It judges faithfulness to the paper, not truth: a false claim stated
   faithfully shows no difference. A clean result is evidence, not a
   substitute for your review. If you edit a statement, rerun
   `backtranslate` on it.
4. **`prove` → `results.json`, `claims/<id>.lean`.** For each claim, the
   outcome:
   - `proved`: the statement holds; the proof is `theorem <id>`.
   - `disproved`: the statement is false; `theorem <id>_false` proves its
     negation, and the notes describe the countermodel.
   - `challenged`: the prover thinks the statement doesn't match the claim;
     nothing was proved. Fix the statement and rerun `prove` on that claim.
   - `open`: no audited proof either way after 4 attempts.

   `results.json` also records the axioms each proof uses (only `propext`,
   `Classical.choice` and `Quot.sound` are allowed) and Lean's own rendering
   of the proved statement.

Every Lean attempt is kept next to its output (`*.attemptN.lean`, with the
compiler output in `*.attemptN.log`), so you can see what was tried.

## Not yet

Planned (see TODO.org): a final report; reviews in Lean and Markdown rather
than JSON; detecting stale outputs; back-translation of the definitions
(checkpoint 2), not only the statements; a guided mode that walks you
through the reviews; multi-file LaTeX and PDF input.
