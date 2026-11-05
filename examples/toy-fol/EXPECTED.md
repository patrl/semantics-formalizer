# Answer key for the translation-style toy paper

Kept out of `paper.tex` so the pipeline never sees it. Example numbers
(1)–(6) are the sentences in the introduction. Notation: S = student,
B = book, R = read.

This paper has **no LFs and no composition rules**: each sentence is
simply assigned FOL translation(s). It tests that the pipeline formalizes
the paper's own route (per-sentence translations, transcribed as given)
rather than inventing a syntax.

## Definitions

Def 1 (models: standard first-order structures, **D non-empty**;
entailment from a set of formulas; contradictoriness). The FOL language
(S, B, R, constant m) is given in running text.

## Examples and their analyses

| Example | Readings | Notes |
|---|---|---|
| (1) Every student read a book. | surface ∀x[Sx → ∃y[By ∧ Rxy]]; inverse ∃y[By ∧ ∀x[Sx → Rxy]] | two readings |
| (2) A student read every book. | surface ∃x[Sx ∧ ∀y[By → Rxy]]; inverse ∀y[By → ∃x[Sx ∧ Rxy]] | two readings |
| (3) Some student read no book. | ∃x[Sx ∧ ¬∃y[By ∧ Rxy]] | |
| (4) No student read every book. | ¬∃x[Sx ∧ ∀y[By → Rxy]] | |
| (5) Mary read every book. | ∀y[By → R m y] | given **only indirectly** ("like the surface reading of (2), with m in place of …"): should be written out and flagged |
| (6) Mary is a student. | S m | given in running text |

## Claims

| Claim | Where | Expected | Why |
|---|---|---|---|
| Prop 1: inverse(1) ⊨ surface(1) | | provable | ∃∀ → ∀∃ |
| Prop 2: surface(2) ⊨ inverse(2) | | provable | ∃∀ → ∀∃ |
| Prop 3: with ≥ 1 student, the readings of (1) are equivalent | | **FALSE** (planted) | Surface ⊭ inverse. Countermodel: students s1, s2; books b1, b2; R = {(s1,b1), (s2,b2)}. Surface true, inverse false. |
| Prop 4: both readings of (2) entail ∃x[Sx ∧ ∀y[By → Rxy]] ("a single student read every book") | | **FALSE** (planted) | True for surface (it *is* surface), false for inverse. Countermodel: same as Prop 3 — inverse(2) true, ∃x∀y false. A faithful statement must cover **both** readings. |
| Prop 5: (4) ≡ ∀x[Sx → ∃y[By ∧ ¬Rxy]] | | provable | Classical quantifier duality |
| (5), (6) ⊨ surface(2) | running text, §4 | provable | m is the witness |
| (4), (5), (6) contradictory | running text, §4 | provable | (5) + (6) make m a student who read every book |
| (3) and surface(2) contradictory | running text, §4 | **FALSE** (planted) | Different students can witness each; or vacuity. Countermodel: D = {s}, S = {s}, no books. Both true. |
| A model with no students verifies both readings of (1) | running text, §4 | **FALSE** (planted) | Inverse is not vacuous: it needs a book. Countermodel: D = {a}, no students, no books. Surface true, inverse false. |

A good pipeline:

- extracts 6 examples (two with two readings each), 1 definition, and 9
  claims, including the 4 in running text;
- writes the translations directly (no LF type, no composition rules) and
  keeps D non-empty, as the paper states;
- proves 5 claims and refutes the 4 planted ones with countermodels like
  those above (each countermodel must have a non-empty domain).
