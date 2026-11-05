You are helping formalize a formal-semantics paper in Lean 4.

Below are the paper's front matter (FRONT MATTER: the start of its LaTeX), its
**definitions** (DEFINITIONS, JSON) and its numbered **examples** with their
LFs (EXAMPLES, JSON), as extracted from its LaTeX. Write a single
self-contained Lean 4 file that formalizes all of them. Later, each of the
paper's claims will be stated and proved on top of this file.

Papers differ a lot in how they set up syntax and interpretation, so follow
**this paper's** conventions, not a standard template:

- Define the paper's LFs as a Lean type in its own terms (its categories,
  node labels, terminals vs. branching nodes, whatever its trees look like),
  and the paper's notion of model.
- Define interpretation **once, generically**: a function computing the
  denotation of any LF from the lexicon by the paper's composition rules
  (by recursion on the LF). Every sentence's meaning must be *computed* from
  its LF this way. Never write a sentence's truth conditions by hand: truth
  conditions the paper derives are claims, to be checked later against
  your interpretation function, not definitions.
- If the paper's rules leave a case open (e.g. which daughter is the
  function, or what happens on a type mismatch), make the interpretation
  reflect that faithfully (e.g. return `Option`) rather than quietly
  deciding it, and note the choice.
- Define each example's LF as `def <id> : … := …`, named **exactly** by its
  `id` from EXAMPLES, transcribing its `lf`.

Constraints:

- Core Lean 4 only: **no Mathlib**, no `import`s. In particular there is no
  `Set` type; represent properties/sets of entities as predicates `D → Prop`.
- Keep the domain of entities arbitrary (a parameter `(D : Type)`, or a
  field of the paper's model), so everything holds for an arbitrary model.
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

--- EXAMPLES ---
{examples}
