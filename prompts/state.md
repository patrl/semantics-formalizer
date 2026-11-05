You are helping formalize a formal-semantics paper in Lean 4.

The paper's definitions have already been formalized in the Lean file below
(DEFINITIONS). Your job is to **state one claim** from the paper (CLAIM, as
extracted from its LaTeX) as a Lean proposition. You are not asked to prove
the claim, or to decide whether it is true: that is a later, separate step.
A faithful statement that turns out to be false is a finding; an unfaithful
statement is a bug.

Faithfulness is the whole point. Never weaken, strengthen, or "fix" the
claim: don't add hypotheses the paper doesn't state (e.g. non-emptiness),
don't drop ones it does, and don't swap in a different definition. If the
paper is ambiguous, pick the most natural reading and say which in `notes`.
Doubts about whether the claim is true also go in `notes`, never into the
statement.

Constraints:

- Return in `statement` a single Lean term of type `Prop`: no `theorem`, no
  proof, no definitions, no commands. It is checked as
  `example : Prop := <statement>` inside `namespace {namespace}`, right
  after DEFINITIONS, so use the vocabulary there directly. Later it becomes
  the type of a theorem exactly as you write it.
- The statement must be closed: bind everything it mentions with `∀` / `∃`,
  including the domain (e.g. `∀ (D : Type) (A B : D → Prop), …`), unless the
  paper's claim is about one specific model.
- Core Lean 4 only, no Mathlib. No `sorry`.

In `notes`, say how you read the claim and list any interpretive choices.
Don't comment on whether the code compiles — it will be compiled for you
and any errors sent back.

--- DEFINITIONS ---
{defs}

--- CLAIM ---
{claim}
