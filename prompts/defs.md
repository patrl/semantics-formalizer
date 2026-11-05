You are helping formalize a formal-semantics paper in Lean 4.

Below are the paper's **definitions**, as extracted from its LaTeX (JSON).
Write a single self-contained Lean 4 file that formalizes all of them. Later,
each of the paper's claims will be stated and proved on top of this file.

Constraints:

- Core Lean 4 only: **no Mathlib**, no `import`s. In particular there is no
  `Set` type; represent properties/sets of entities as predicates `D → Prop`.
- Fix the domain of entities as a variable `(D : Type)` (or a `variable`
  declaration), so everything holds for an arbitrary model.
- Use `Prop` for truth values: "δ(A)(B) = 1" becomes the proposition `δ A B`.
  Where the paper equates truth values, use `↔`.
- Be **faithful**: formalize what the paper says, not what you think it should
  say. Don't add hypotheses (e.g. non-emptiness) the paper doesn't state.
  Where the paper is underspecified, pick the most natural reading and say
  which one in a comment.
- Use readable names that echo the paper (`every`, `Conservative`, …) and put
  a `/-- … -/` docstring on each definition citing its label (e.g. "Definition 2").
- Definitions only: no theorems, no `sorry`.

Return the full file contents in `lean`, and in `notes` list every
interpretive choice you made (one line each). Don't comment on whether the
code compiles — the file will be compiled for you and any errors sent back.

--- DEFINITIONS ---
