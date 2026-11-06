You will read a Lean 4 proposition and say in plain English exactly what it
says.

Below are some Lean definitions (DEFINITIONS) and a proposition stated on top
of them (STATEMENT). They are all you have: you are not told where they come
from or what they are meant to capture, and you should not guess. Say what
the Lean says, not what it was probably meant to say. If it looks odd or
mistaken, translate it faithfully anyway; don't correct it or point it out.

Write in the register of a formal-semantics paper, and be exact about:

- every quantifier and its scope, and what it ranges over (e.g. all
  domains, all models, only models meeting some condition);
- every hypothesis, including ones hidden inside a definition;
- the direction of each implication, entailment or biconditional;
- edge cases the definitions decide: an empty domain, an undefined value
  (e.g. `none`) and how it is treated, vacuous truth.

Give two readings:

- `surface`: what STATEMENT says in the vocabulary of DEFINITIONS, using
  the defined notions as they are (e.g. "for every model `M`, if `s1` is
  true in `M` then `s2` is true in `M`"). Refer to defined objects by
  their Lean names.
- `unfolded`: the same, with every defined notion the statement depends on
  expanded through DEFINITIONS, down to conditions on models and their
  domains. Where the statement mentions a sentence, a formula or another
  representation, work out the meaning the definitions compute for it and
  write that out (e.g. "every individual that is a dog barked", not "`s1`
  is true"). Expand defined relations (entailment, consistency, …) and
  properties the same way.

--- DEFINITIONS ---
{defs}

--- STATEMENT ---
{statement}
