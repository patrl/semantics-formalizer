# Answer key for the toy paper

Kept out of `paper.tex` so the pipeline never sees it. Example numbers
(1)–(6) are the sentences in the introduction.

## Definitions

Def 1 (lexicon), Def 2 (TN + FA), Def 3 (meaning postulate: phonologist ⊆
linguist), Def 4 (entailment / contradictoriness, quantifying over models
that respect Def 3), Def 5 (conservativity), Def 6 (monotonicity; MON↓ only
"defined analogously").

## Claims

| Claim | Where | Expected | Why |
|---|---|---|---|
| TC of (1): ann sneezed | running text, §3 | provable | — |
| TC of (2): ∀x[linguist x → sneezed x] | displayed derivation, §3 | provable | — |
| TC of (3): ∃x[linguist x ∧ sneezed x] | running text, §3 | provable | — |
| TC of (4): ∃x[linguist x ∧ ¬sneezed x] | running text, §3 | **FALSE** (planted) | Mis-derived: that's *not every linguist sneezed*. Lexicon gives ¬∃x[linguist x ∧ sneezed x]. Counterexample: no linguists — (4) true, paper's TC false. |
| Prop 1 (conservativity) | | provable | — |
| Prop 2 (every ↓MON, MON↑) | | provable | — |
| Prop 3 (no ↓MON, MON↓) | | provable | — |
| Prop 4 (some ↓MON) | | **FALSE** (planted) | `some` is ↑MON. Counterexample: A = {a}, B = {a}, A' = ∅. |
| Prediction 1: (2) ⊨ (5) | | provable | every ↓MON + postulate. |
| (3) ⊨ (6) | running text, §5 | **FALSE** (planted) | Rests on false Prop 4. Counterexample: one linguist who sneezed, no phonologists. |
| Prediction 2: (6) ⊨ (3) | | provable | some is ↑MON (left) + postulate — true even though the paper never states ↑MON. |
| Prediction 3: ann linguist ⇒ ((2) ⊨ (1)) | | provable | — |
| Prediction 4: (3), (4) contradictory | | provable | True from the **lexicon**; false if you trust the paper's mis-derived TC of (4). Tests whether claims are formalized against the lexicon. |
| (2) ⊨ (3) | running text, §5 | **FALSE** (planted) | No existential import: model with no linguists. |

A good pipeline proves 10 claims and disproves the 4 planted ones, and
finds the unlabeled claims in running text (TCs of (1), (3), (4); (3) ⊨ (6);
(2) ⊨ (3)).
