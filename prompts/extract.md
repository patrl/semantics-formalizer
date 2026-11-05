You are helping formalize a formal-semantics paper in Lean 4.

Below is the LaTeX source of the paper. Extract every **definition** and every
**claim** (proposition, theorem, lemma, corollary, fact, or an informal
entailment claim stated in running text) in the order it appears.

For each item give:

- `id`: a short stable identifier, e.g. `def1`, `prop3` (use the paper's own
  numbering where it has one).
- `kind`: `"definition"` or `"claim"`.
- `label`: the paper's own name for it, e.g. `"Proposition 3"`.
- `latex`: the exact LaTeX of the item, copied verbatim.
- `statement`: a precise, self-contained plain-English restatement. Spell out
  quantifiers and expand any notation, but do **not** fix, strengthen, or
  weaken the claim — transcribe what the paper says, even if you think it is
  wrong.
- `depends_on`: ids of earlier definitions this item uses.
- `concerns`: anything ambiguous, underspecified, or possibly false about the
  item as stated (empty string if none). This is where doubts go — not into
  `statement`.

--- PAPER ---
