You are checking whether a formalization of a claim says what the paper
says.

One claim from a formal-semantics paper (CLAIM, its LaTeX) has been
formalized in Lean. Someone who saw **only the Lean**, not the paper, then
wrote what the formalization says, at two depths:

- SURFACE: in the formalization's own vocabulary;
- UNFOLDED: with its definitions expanded down to truth conditions over
  models.

Compare each reading with CLAIM, read in the context of the whole paper
(PAPER, its LaTeX): its definitions, its examples and the representations
(LFs, translations) it assigns them. For the unfolded reading, expand CLAIM
through the paper's definitions in the same way and compare the results.

The question is only whether they say the same thing, **not whether the
claim is true**. Papers make mistakes: a false claim, or a truth condition
the paper derives wrongly, that is formalized faithfully shows no
difference. Compare against what the paper says, even where you think the
paper is wrong.

List every difference as one entry, saying which reading it concerns and
classing it as:

- `substantive`: the truth conditions differ. There is a model on which
  one is true and the other false: an added or missing hypothesis, a
  different quantifier or scope, a narrower or wider domain, a reversed
  direction, a different meaning computed for a sentence. Give such a
  model in `model` where you can.
- `choice`: the paper's own text supports more than one reading here, and
  the formalization takes one of them. Say what the other reading is. Not
  for something the paper simply doesn't say: an added hypothesis or a
  narrower domain is `substantive`, even if it is a common convention.

The paper's definitions govern. If the formalization disagrees with them,
that is `substantive`, even where it agrees with something the paper
derives or claims elsewhere (derived claims are what is being checked).
- `wording`: phrasing, notation, naming, order, or how something is
  represented (e.g. sets as predicates, truth values as propositions,
  quantifying over all domains for "in any model") differ, but the truth
  conditions are the same.

If there is no difference, return an empty list. Don't list things that
agree.

--- PAPER ---
{paper}

--- CLAIM ---
{claim}

--- SURFACE ---
{surface}

--- UNFOLDED ---
{unfolded}
