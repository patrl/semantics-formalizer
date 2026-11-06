You are helping formalize a formal-semantics paper in Lean 4.

Below is the LaTeX source of the paper. Extract, in the order they appear:

- every **definition**: numbered definitions, and also unnumbered
  stipulations that later material relies on (e.g. the type theory, what a
  model is, the representation language, general conventions for LFs or
  translations stated in running text). The representation of a particular
  sentence is not a definition: it goes in that example's `analysis`;
- every **example**: each numbered example sentence, e.g. `\ex` items or
  `(1)`, `(2)`, … in an `exe`/`examples` environment. A representation the
  paper assigns to a sentence (an LF, or a translation into first-order
  logic or another representation language) is part of that example, not a
  separate item;
- every **claim**: proposition, theorem, lemma, corollary, fact, prediction,
  derived truth condition, or an informal claim stated in running text (e.g.
  "so (2) entails (3)", "this gives the truth conditions …"). Only
  statements that could be true or false of the paper's definitions: not
  signposting or programmatic remarks ("these properties yield predictions").

A justification or proof sketch ("This follows from Proposition 2 together
with Definition 3") is not an item of its own: record the claims it cites in
`cites` on the item it justifies.

For each item give:

- `id`: a short stable identifier, e.g. `def1`, `prop3`, `ex2` (use the
  paper's own numbering where it has one).
- `kind`: `"definition"`, `"example"`, or `"claim"`.
- `label`: the paper's own name for it, e.g. `"Proposition 3"`, `"(2)"`, or
  a short description for unlabelled items, e.g. `"Truth conditions of (3)"`.
- `latex`: the item's LaTeX, copied **verbatim** as one contiguous span of
  the source (it will be located in the source mechanically, so don't
  reformat, abridge, or expand macros). For an item stated in running text,
  the shortest contiguous span that contains it.
- `statement`: a precise, self-contained plain-English restatement. Spell out
  quantifiers and expand any notation, but do **not** fix, strengthen, or
  weaken the item — transcribe what the paper says, even if you think it is
  wrong. For an example, the sentence itself.
- `analysis`: for an example, the representation(s) the paper assigns to
  it, in the paper's own notation, each prefixed by what it is, e.g.
  `LF: [S [DP every linguist] sneezed]` or
  `FOL: ∀x[linguist(x) → sneezed(x)]` (one per line if there are several,
  e.g. two readings); for anything else, an empty string. If the paper
  gives it only indirectly ("(3)–(6) are parallel"), write it out and say so
  in `concerns`. If the paper gives none, leave it empty and say so in
  `concerns`. Truth conditions the paper *derives* from a representation
  are claims, not part of `analysis`.
- `depends_on`: ids of earlier definitions and examples this item uses.
  Never claims: if the item relies on an earlier claim (e.g. a prediction
  that rests on a derived truth condition), put that claim in `cites`.
- `cites`: ids of claims this item follows from or relies on, whether the
  paper says so explicitly ("by Proposition 4, …") or plainly uses them;
  empty if none.
- `concerns`: anything ambiguous, underspecified, or possibly false about the
  item as stated (empty string if none). This is where doubts go — not into
  `statement`. Only doubts: don't note that an item is true, or that the
  paper gives no proof.

--- PAPER ---
