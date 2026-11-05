You are helping formalize a formal-semantics paper in Lean 4.

Below are the paper's front matter (FRONT MATTER: the start of its LaTeX) and
its **definitions**, as extracted from its LaTeX (DEFINITIONS, JSON). Write a
single self-contained Lean 4 file that formalizes all of them. Later, each of
the paper's claims will be stated and proved on top of this file.

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
- Wrap the whole file in a **namespace specific to this paper**, so its names
  can't clash with formalizations of other papers: an UpperCamelCase
  identifier built from the authors and year (e.g. `BarwiseCooper1981`) or,
  failing that, the title (e.g. `DeterminersAsRelations`) — never a generic
  name like `Semantics`. The first line of code must be `namespace <Name>` and
  the last `end <Name>`. Nested namespaces inside it are fine.
- Definitions only: no theorems, no `sorry`.

Return the full file contents in `lean`, the namespace in `namespace`, and in
`notes` list every interpretive choice you made (one line each). Don't comment
on whether the code compiles — the file will be compiled for you and any
errors sent back.

--- FRONT MATTER ---
{front_matter}

--- DEFINITIONS ---
{definitions}
