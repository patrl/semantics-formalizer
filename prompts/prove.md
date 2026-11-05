You are helping formalize a formal-semantics paper in Lean 4.

The paper's definitions have already been formalized in the Lean file below
(DEFINITIONS). One of the paper's claims (CLAIM, as extracted from its LaTeX)
has been stated in Lean, and the statement has been approved as faithful
(STATEMENT). Your job is to **settle STATEMENT**: prove it or refute it.

STATEMENT is fixed. You don't write it: you supply only the proof, and the
theorem it proves is assembled for you. First decide whether STATEMENT is
true.

- If it is true: set `verdict` to `"proved"`. Your proof is checked as
  `theorem {id} : STATEMENT := <proof>`.
- If it is false: set `verdict` to `"disproved"`. Your proof is checked as
  `theorem {id}_false : ¬ (STATEMENT) := <proof>`, typically by exhibiting a
  counterexample.
- If you believe STATEMENT does not say what CLAIM says (a missing or extra
  hypothesis, a different quantifier or scope, …): set `verdict` to
  `"challenge"`, leave `helpers` and `proof` empty, and explain the
  mismatch in `notes`. The statement goes back to the user for review.
  Don't challenge a statement because it is hard to prove, or because you
  think the paper is wrong: a faithful statement that is false gets
  `"disproved"`.

Constraints:

- `proof` is the text after `:=`, e.g. `by` followed by a tactic block.
  `helpers` (may be empty) is placed before the theorem: helper lemmas and
  theorems only. Both go inside `namespace {namespace}`, right after
  DEFINITIONS; don't repeat anything from it, and don't add `import`s.
- Core Lean 4 only, no Mathlib. No `sorry`, `admit`, `axiom`,
  `native_decide`, `unsafe`, `implemented_by`, or `extern`.
- **No new definitions** (`def`, `abbrev`, `structure`, `inductive`,
  `instance`, `notation`, …), and nothing that changes how names or
  notation are resolved (`open`, `export`, `attribute`, `set_option`,
  `local`, `scoped`, `variable`, `section`, `namespace`, `end`).
- For a counterexample you'll need a concrete domain, e.g. `Bool` or `Unit`;
  write concrete properties inline as lambdas (`fun x => …`).
- Your code is audited automatically: the theorem may only depend on Lean's
  standard axioms (`propext`, `Classical.choice`, `Quot.sound`).

In `notes`, briefly explain the verdict (and the counterexample, if any, in
the paper's own terms). Don't comment on whether the code compiles — it will
be compiled for you and any errors sent back.

--- DEFINITIONS ---
{defs}

--- CLAIM ---
{claim}

--- STATEMENT ---
{statement}
