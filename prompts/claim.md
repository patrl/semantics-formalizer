You are helping formalize a formal-semantics paper in Lean 4.

The paper's definitions have already been formalized in the Lean file below
(DEFINITIONS). Your job is to formalize **one claim** from the paper (CLAIM,
as extracted from its LaTeX) and settle it in Lean.

First decide whether the claim, **exactly as stated**, is true under these
definitions.

- If it is true: set `verdict` to `"proved"` and write a theorem named
  `{id}` whose statement is a faithful formalization of the claim, with a
  complete proof.
- If it is false: set `verdict` to `"disproved"` and write a theorem named
  `{id}_false` whose statement is `¬ (…)` where `(…)` is the faithful
  formalization of the claim, with a complete proof (typically by
  exhibiting a counterexample).

Faithfulness is the whole point. Never weaken or "fix" the claim to make it
provable: don't add hypotheses the paper doesn't state, don't swap in a
different definition. If the paper is ambiguous, pick the most natural
reading and say which in `notes`.

Constraints:

- Your code is **appended** to the DEFINITIONS file, so don't repeat or
  redefine anything from it, and don't add `import`s. Put all your code
  inside `namespace {namespace} … end {namespace}`, the paper's namespace.
- Core Lean 4 only, no Mathlib. No `sorry`, `admit`, `axiom`,
  `native_decide`, `unsafe`, `implemented_by`, or `extern`.
- **No new definitions** (`def`, `abbrev`, `structure`, `inductive`,
  `instance`, `notation`, …): state the claim using the vocabulary in
  DEFINITIONS. You may add helper lemmas/theorems before the main theorem.
- For a counterexample you'll need a concrete domain, e.g. `Bool` or `Unit`;
  write concrete properties inline as lambdas (`fun x => …`).
- Your code is audited automatically: the main theorem may only depend on
  Lean's standard axioms (`propext`, `Classical.choice`, `Quot.sound`).

Return only your appended code in `lean`. In `notes`, briefly explain the
verdict (and the counterexample, if any) and any interpretive choices. Don't
comment on whether the code compiles — it will be compiled for you and any
errors sent back.

--- DEFINITIONS ---
{defs}

--- CLAIM ---
{claim}
