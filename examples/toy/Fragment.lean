/-
  Hand-written prototype: an executable version of the toy fragment.

  ⟦·⟧ is computed from LF trees by the paper's own rules (TN + FA), over
  finite models, with D_t = Bool. `#eval` then shows, sentence by sentence,
  whether the paper's predictions go through, by searching all models up to
  a given size for a countermodel.

  Run with: lean examples/toy/Fragment.lean
-/

namespace Fragment

/-! ## Types and models -/

inductive Ty where
  | e | t
  | fn (σ τ : Ty)
  deriving DecidableEq, Repr

/-- A model: D_e = `Fin size`, plus the interpretation of the non-logical
vocabulary. Since ⟦Ann⟧ ∈ D_e, every model has at least one entity. -/
structure Model where
  size : Nat
  ann : Fin size
  linguist : Fin size → Bool
  phonologist : Fin size → Bool
  sneezed : Fin size → Bool

/-- D_σ relative to a model. -/
def Ty.den (M : Model) : Ty → Type
  | .e => Fin M.size
  | .t => Bool
  | .fn σ τ => σ.den M → τ.den M

/-- Definition 3 (meaning postulate): phonologists are linguists. -/
def Model.admissible (M : Model) : Bool :=
  decide (∀ x, M.phonologist x = true → M.linguist x = true)

/-! ## Lexicon (Definition 1) -/

inductive Word where
  | ann | linguist | phonologist | sneezed | every | some | no
  deriving DecidableEq, Repr

def Word.ty : Word → Ty
  | .ann => .e
  | .linguist | .phonologist | .sneezed => .fn .e .t
  | .every | .some | .no => .fn (.fn .e .t) (.fn (.fn .e .t) .t)

def Word.den (M : Model) : (w : Word) → w.ty.den M
  | .ann => M.ann
  | .linguist => M.linguist
  | .phonologist => M.phonologist
  | .sneezed => M.sneezed
  | .every => fun (f g : Fin M.size → Bool) => decide (∀ x : Fin M.size, f x = true → g x = true)
  | .some => fun (f g : Fin M.size → Bool) => decide (∃ x : Fin M.size, f x = true ∧ g x = true)
  | .no => fun (f g : Fin M.size → Bool) => !decide (∃ x : Fin M.size, f x = true ∧ g x = true)

/-! ## LFs and composition (Definition 2) -/

inductive Tree where
  | leaf (w : Word)
  | node (l r : Tree)

/-- A typed denotation: a type together with an element of its domain. -/
abbrev Den (M : Model) := (τ : Ty) × τ.den M

/-- FA, one direction: apply `f` to `x` if their types fit. -/
def apply (M : Model) : Den M → Den M → Option (Den M)
  | ⟨.fn σ τ, f⟩, ⟨σ', x⟩ => if h : σ' = σ then some ⟨τ, f (h ▸ x)⟩ else none
  | _, _ => none

/-- ⟦·⟧: TN at the leaves, FA (in whichever order typechecks) at branching
nodes. `none` means the tree is uninterpretable. -/
def interp (M : Model) : Tree → Option (Den M)
  | .leaf w => some ⟨w.ty, w.den M⟩
  | .node l r => do
      let a ← interp M l
      let b ← interp M r
      (apply M a b).orElse fun _ => apply M b a

/-- Truth value of a sentence (`none` if it isn't of type t). -/
def truth (M : Model) (s : Tree) : Option Bool :=
  match interp M s with
  | some ⟨.t, b⟩ => some b
  | _ => none

/-! ## The numbered examples, as LFs -/

open Tree Word in
def ex : Nat → Tree
  | 1 => node (leaf ann) (leaf sneezed)                             -- Ann sneezed.
  | 2 => node (node (leaf every) (leaf linguist)) (leaf sneezed)    -- Every linguist sneezed.
  | 3 => node (node (leaf some) (leaf linguist)) (leaf sneezed)     -- Some linguist sneezed.
  | 4 => node (node (leaf no) (leaf linguist)) (leaf sneezed)       -- No linguist sneezed.
  | 5 => node (node (leaf every) (leaf phonologist)) (leaf sneezed) -- Every phonologist sneezed.
  | 6 => node (node (leaf some) (leaf phonologist)) (leaf sneezed)  -- Some phonologist sneezed.
  | _ => leaf ann

/-! ## Enumerating models and searching for countermodels -/

/-- All models with exactly `n` entities (n ≥ 1). Each predicate is one of the
2^n subsets of D_e, encoded as a bitmask. -/
def modelsOfSize (n : Nat) : List Model :=
  if 0 < n then
    let subsets := (List.range (2 ^ n)).map fun m (x : Fin n) => m.testBit x.val
    (List.finRange n).flatMap fun a =>
      subsets.flatMap fun l => subsets.flatMap fun p => subsets.map fun s =>
        { size := n, ann := a, linguist := l, phonologist := p, sneezed := s }
  else []

/-- All admissible models with 1..maxSize entities. -/
def models (maxSize : Nat) : List Model :=
  ((List.range maxSize).flatMap fun k => modelsOfSize (k + 1)).filter (·.admissible)

/-- First admissible model (up to `maxSize`) satisfying `cond`. -/
def findModel (cond : Model → Bool) (maxSize := 3) : Option Model :=
  (models maxSize).find? cond

/-! ## Pretty-printing -/

def ext (M : Model) (p : Fin M.size → Bool) : List Nat :=
  (List.finRange M.size).filter p |>.map (·.val)

instance : ToString Model where
  toString M := s!"D_e = {(List.range M.size)}, ann = {M.ann.val}, " ++
    s!"linguist = {ext M M.linguist}, phonologist = {ext M M.phonologist}, " ++
    s!"sneezed = {ext M M.sneezed}"

def showTruth : Option Bool → String
  | some true => "1" | some false => "0" | none => "undefined"

/-- S₁,…,Sₖ ⊨ S (optionally only in models satisfying `side`): report ✓ or a
countermodel with the truth value of every sentence involved. -/
def checkEntails (label : String) (premises : List Nat) (concl : Nat)
    (side : Model → Bool := fun _ => true) (maxSize := 3) : String :=
  let bad M := side M && premises.all (fun i => truth M (ex i) == some true) && truth M (ex concl) != some true
  match findModel bad maxSize with
  | none => s!"✓ {label}: no countermodel with ≤ {maxSize} entities"
  | some M =>
    let vals := (premises ++ [concl]).map fun i => s!"⟦({i})⟧ = {showTruth (truth M (ex i))}"
    s!"✗ {label}: countermodel  {M}\n    {", ".intercalate vals}"

/-- S₁ and S₂ contradictory: report ✓ or a model where both are true. -/
def checkContradictory (label : String) (a b : Nat) (maxSize := 3) : String :=
  match findModel (fun M => truth M (ex a) == some true && truth M (ex b) == some true) maxSize with
  | none => s!"✓ {label}: no model with ≤ {maxSize} entities makes both true"
  | some M => s!"✗ {label}: both true in  {M}"

/-- Compare the derived truth value of a sentence with the paper's stated
truth conditions, in every model up to `maxSize`. -/
def checkTC (label : String) (i : Nat) (stated : Model → Bool) (maxSize := 3) : String :=
  match findModel (fun M => truth M (ex i) != some (stated M)) maxSize with
  | none => s!"✓ {label}: derived = stated in every model with ≤ {maxSize} entities"
  | some M =>
    s!"✗ {label}: countermodel  {M}\n    derived ⟦({i})⟧ = {showTruth (truth M (ex i))}, stated = {showTruth (some (stated M))}"

/-! ## A single model, by hand -/

/-- Two linguists, 0 and 1; only 0 sneezed. -/
def M₀ : Model :=
  { size := 2, ann := 0,
    linguist := fun _ => true, phonologist := fun x => x == 1, sneezed := fun x => x == 0 }

#eval IO.println s!"M₀: {M₀}"
#eval IO.println <| ", ".intercalate <| (List.range 6).map fun i => s!"⟦({i+1})⟧ = {showTruth (truth M₀ (ex (i+1)))}"

/-! ## The paper's claims about sentences -/

-- §3: truth conditions as stated in the paper
#eval IO.println <| checkTC "TC of (1)" 1 fun M => M.sneezed M.ann
#eval IO.println <| checkTC "TC of (2)" 2 fun M => decide (∀ x, M.linguist x = true → M.sneezed x = true)
#eval IO.println <| checkTC "TC of (3)" 3 fun M => decide (∃ x, M.linguist x = true ∧ M.sneezed x = true)
#eval IO.println <| checkTC "TC of (4)" 4 fun M => decide (∃ x, M.linguist x = true ∧ M.sneezed x = false)

-- §5: predictions
#eval IO.println <| checkEntails "Prediction 1: (2) ⊨ (5)" [2] 5
#eval IO.println <| checkEntails "(3) ⊨ (6)  [running text]" [3] 6
#eval IO.println <| checkEntails "Prediction 2: (6) ⊨ (3)" [6] 3
#eval IO.println <| checkEntails "Prediction 3: (2) ⊨ (1), if ann is a linguist" [2] 1
  (side := fun M => M.linguist M.ann)
#eval IO.println <| checkContradictory "Prediction 4: (3), (4) contradictory" 3 4
#eval IO.println <| checkEntails "(2) ⊨ (3)  [running text]" [2] 3

end Fragment
