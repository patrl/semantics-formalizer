You are helping formalize a formal-semantics paper in Lean 4.

Below are the paper's front matter (FRONT MATTER: the start of its LaTeX), its
**definitions** (DEFINITIONS, JSON) and its numbered **examples** with the
representations it assigns them (EXAMPLES, JSON, field `analysis`), as
extracted from its LaTeX. Write a single
self-contained Lean 4 file that formalizes all of them. Later, each of the
paper's claims will be stated and proved on top of this file.

Papers differ a lot in how they get from sentences to meanings: LFs
interpreted by composition rules, intuitive translations into first-order
logic or another representation language, translation rules, or a mix.
Follow **this paper's** route, not a standard template, and formalize only
the machinery it actually has (don't invent LFs for a paper that only gives
translations):

- Define the paper's notion of model, and whatever representations it uses
  (e.g. an LF tree type in its own categories and labels, or the syntax of
  its logic), in its own terms.
- Where the paper gives a **procedure** from representations to meanings
  (composition rules, a semantics for its logic, translation rules), define
  it **once, generically** (by recursion on the representation) and compute
  every example's meaning through it. Never write such a meaning out by
  hand: truth conditions the paper derives are claims, to be checked later
  against your definitions.
- Where the paper simply **assigns** a representation to a sentence (an
  intuitive translation into FOL, say), that assignment is the paper's
  analysis: transcribe it as given. If the paper's logic is standard and
  its claims are only about what sentences mean, you may render a
  translation directly as a Lean proposition about a model; if any claim is
  about the representations themselves (scope, variable binding, the
  translation), define their syntax and interpretation instead.
- If the paper's rules leave a case open (e.g. which daughter is the
  function, or what happens on a type mismatch), make the definitions
  reflect that faithfully (e.g. return `Option`) rather than quietly
  deciding it, and note the choice.
- Define each example as `def <id> … := …`, named **exactly** by its `id`
  from EXAMPLES, holding its representation as given in `analysis` (an LF,
  a formula, or the translation's meaning). If it has several readings,
  define one per reading (`<id>_a`, `<id>_b`, …) and make `<id>` list them.

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
