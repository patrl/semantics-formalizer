#!/usr/bin/env python3
"""Planted unfaithful variants for the blind back-translation (SPEC.md §10).

Copies the toy v2 run (runs/toy: claims.json, Defs.lean, statements.json),
plants one unfaithful change per variant, and runs `backtranslate` on the
claims it affects. Every variant must be flagged (a substantive difference).
Makes live model calls (two per claim checked).

    python3 tests/backtranslate_variants.py [variant ...]
"""

import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("formalize", ROOT / "formalize.py")
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)

SOURCE = ROOT / "runs" / "toy"
PAPER = ROOT / "examples" / "toy" / "paper.tex"

# name: (statement edits {claim: new statement}, Defs.lean edits [(old, new)],
#        claims to check)
VARIANTS = {
    # Claim statements.
    # An added non-emptiness hypothesis. Not `Nonempty D`: every `Model D`
    # has `ann : D`, so that would change nothing (the comparer said so).
    "nonempty-hypothesis": (
        {"claim_every_some": "∀ (D : Type) (M : Model D), MeaningPostulate M → "
                             "(∃ x, M.linguist x) → TrueIn M ex2 → TrueIn M ex3"},
        [], ["claim_every_some"]),
    "prop4-every-for-some": (
        {"prop4": "∀ (D : Type), LeftDownMON (every : Det D)"},
        [], ["prop4"]),
    "tc4-negation-scope": (
        {"tc4": "∀ (D : Type) (M : Model D), TrueIn M ex4 ↔ "
                "¬ ∃ x : D, M.linguist x ∧ M.sneezed x"},
        [], ["tc4"]),
    # Definitions only: the statements that use them are unchanged.
    "every-existential-import": (
        {}, [("def every {D : Type} : Det D := fun f g => ∀ x, f x → g x",
              "def every {D : Type} : Det D := fun f g => (∃ x, f x) ∧ ∀ x, f x → g x")],
        ["claim_every_some", "tc2"]),
    "no-negation-scope": (
        {}, [("def no {D : Type} : Det D := fun f g => ¬ ∃ x, f x ∧ g x",
              "def no {D : Type} : Det D := fun f g => ∃ x, f x ∧ ¬ g x")],
        ["pred4"]),
}


def run_variant(name: str, base: Path) -> dict[str, bool]:
    stmt_edits, defs_edits, check = VARIANTS[name]
    run_dir = base / name
    run_dir.mkdir()
    for f in ("claims.json", "Defs.lean", "statements.json"):
        shutil.copy(SOURCE / f, run_dir / f)
    defs = (run_dir / "Defs.lean").read_text()
    for old, new in defs_edits:
        assert old in defs, f"{name}: Defs.lean has no `{old}`"
        defs = defs.replace(old, new)
    (run_dir / "Defs.lean").write_text(defs)
    statements = json.loads((run_dir / "statements.json").read_text())
    for cid, new in stmt_edits.items():
        statements[cid]["statement"] = new
    (run_dir / "statements.json").write_text(json.dumps(statements, ensure_ascii=False))

    # The variant must still be well-typed Lean, or it tests nothing.
    ns = F.paper_namespace(defs)
    check_file = run_dir / "Check.lean"
    check_file.write_text(defs + "".join(
        f"\nnamespace {ns}\nexample : Prop := {statements[c]['statement']}\nend {ns}\n"
        for c in check))
    ok, log = F.compile_lean(check_file)
    assert ok, f"{name}: variant doesn't compile:\n{log}"

    print(f"\n=== {name}")
    for cid in check:
        F.backtranslate(PAPER, run_dir, cid)
    results = json.loads((run_dir / "backtranslations.json").read_text())
    return {cid: results[cid]["flagged"] for cid in check}


if __name__ == "__main__":
    names = sys.argv[1:] or list(VARIANTS)
    with tempfile.TemporaryDirectory() as d:
        outcome = {n: run_variant(n, Path(d)) for n in names}
    print("\nvariants (each must be FLAGGED):")
    for n, flags in outcome.items():
        for cid, flagged in flags.items():
            print(f"  {n:26} {cid:18} {'FLAGGED' if flagged else 'MISSED'}")
    sys.exit(0 if all(all(f.values()) for f in outcome.values()) else 1)
