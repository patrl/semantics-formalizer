# Answer key for the toy paper

Kept out of `paper.tex` so the pipeline never sees it.

| Result | Expected | Why |
|---|---|---|
| Def 1–3 | definitions | — |
| Prop 1 (conservativity) | provable | — |
| Prop 2 (every ↓MON, MON↑) | provable | — |
| Prop 3 (no ↓MON, MON↓) | provable | — |
| Prop 4 (some ↓MON) | **FALSE** (planted) | `some` is ↑MON. Counterexample: A = {a}, B = {a}, A' = ∅. |
| Prop 5 (every ⇒ some) | **FALSE as stated** (planted) | Fails when A = ∅ (no existential import). Holds only with the extra premise A ≠ ∅. |
| Prop 6 (instantiation) | provable | — |

A good pipeline should prove 1, 2, 3 and 6, and flag 4 and 5 rather than
quietly proving something weaker.
