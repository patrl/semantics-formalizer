#!/usr/bin/env python3
"""Barebones auto-formalizer for semantics papers.

Usage:
    python3 formalize.py extract examples/toy/paper.tex   # -> claims.json
    python3 formalize.py defs    examples/toy/paper.tex   # -> Defs.lean
    python3 formalize.py claims  examples/toy/paper.tex [claim-id]
                                                  # -> claims/<id>.lean, results.json

Every step writes its output under runs/<paper-name>/ so you can inspect it.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
PROMPTS = ROOT / "prompts"
RUNS = ROOT / "runs"


def call_claude(prompt: str, schema: dict) -> dict:
    """Send one prompt to `claude -p` (no tools) and return its JSON answer."""
    cmd = [
        "claude", "-p",
        "--tools", "",                  # pure text-in/text-out, no file access
        "--no-session-persistence",
        "--output-format", "json",
        "--json-schema", json.dumps(schema),
    ]
    out = subprocess.run(cmd, input=prompt, capture_output=True, text=True, check=True)
    reply = json.loads(out.stdout)
    if reply.get("is_error"):
        sys.exit(f"claude returned an error: {reply.get('result')}")
    print(f"  (cost ${reply['total_cost_usd']:.3f}, {reply['duration_ms'] / 1000:.0f}s)")
    return reply["structured_output"]


# --- Step 1: extract ---------------------------------------------------------

CLAIMS_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "kind": {"enum": ["definition", "claim"]},
                    "label": {"type": "string"},
                    "latex": {"type": "string"},
                    "statement": {"type": "string"},
                    "depends_on": {"type": "array", "items": {"type": "string"}},
                    "concerns": {"type": "string"},
                },
                "required": ["id", "kind", "label", "latex", "statement",
                             "depends_on", "concerns"],
            },
        }
    },
    "required": ["items"],
}


def extract(paper: Path, run_dir: Path) -> None:
    print(f"extract: {paper} -> {run_dir}/claims.json")
    prompt = (PROMPTS / "extract.md").read_text() + paper.read_text()
    result = call_claude(prompt, CLAIMS_SCHEMA)
    (run_dir / "claims.json").write_text(json.dumps(result, indent=2) + "\n")
    for item in result["items"]:
        flag = "  ⚠ " + item["concerns"] if item["concerns"] else ""
        print(f"  {item['id']:8} {item['kind']:10} {item['label']}{flag}")


# --- Lean compile loop -------------------------------------------------------

MAX_ATTEMPTS = 4

LEAN_SCHEMA = {
    "type": "object",
    "properties": {"lean": {"type": "string"}, "notes": {"type": "string"}},
    "required": ["lean", "notes"],
}


def compile_lean(path: Path) -> tuple[bool, str]:
    """Run `lean` on a file. Returns (ok, compiler output). `sorry` counts as failure."""
    out = subprocess.run(["lean", path.name], cwd=path.parent,
                         capture_output=True, text=True, timeout=300)
    log = out.stdout + out.stderr
    return out.returncode == 0 and "sorry" not in log, log


def shift_line_numbers(log: str, name: str, offset: int) -> str:
    """Rewrite `name:LINE:COL:` locations so they count from the model's own code."""
    return re.sub(rf"{re.escape(name)}:(\d+):",
                  lambda m: f"{name}:{int(m.group(1)) - offset}:", log)


# --- Audit: catch proofs that compile but cheat --------------------------------

# Lean's three standard axioms. Anything else a proof depends on (sorryAx, an
# `axiom` the model declared, native_decide's generated axiom, ...) is rejected.
ALLOWED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}

# Regexes run over the model's code (comments stripped). Each match is a problem.
ESCAPE_HATCHES = [r"\bsorry\b", r"\badmit\b", r"\baxiom\b", r"\bnative_decide\b",
                  r"\bunsafe\b", r"\bimplemented_by\b", r"\bextern\b"]
# Claims must be stated in the vocabulary of Defs.lean, not new definitions
# (which could quietly shadow or replace the paper's).
NEW_DEFINITIONS = [r"(?m)^\s*(?:@\[[^\]]*\]\s*)?(?:(?:private|protected|noncomputable)\s+)*"
                   r"(?:def|abbrev|structure|inductive|class|instance|opaque"
                   r"|notation|infix\w*|prefix|postfix|macro|syntax)\b"]


def strip_comments(code: str) -> str:
    code = re.sub(r"/-.*?-/", "", code, flags=re.S)
    return re.sub(r"--.*", "", code)


def audit(code: str, log: str, forbidden: list[str],
          theorem: str | None) -> tuple[list[str], dict]:
    """Check the model's code and Lean's output. Returns (problems, facts)."""
    problems, facts = [], {}
    bare = strip_comments(code)
    for pattern in forbidden:
        for m in re.finditer(pattern, bare):
            problems.append(f"forbidden construct `{m.group(0).strip()}` in your code")
    if theorem:
        m = re.search(rf"^'{re.escape(theorem)}' (?:depends on axioms: \[(.*)\]"
                      r"|does not depend on any axioms)$", log, re.M)
        if not m:
            problems.append(f"no theorem named `{theorem}` was found")
        else:
            axioms = [a.strip() for a in (m.group(1) or "").split(",") if a.strip()]
            facts["axioms"] = axioms
            bad = [a for a in axioms if a not in ALLOWED_AXIOMS]
            if bad:
                problems.append(f"`{theorem}` depends on disallowed axioms: {bad}")
            # `#check @theorem` comes right after, so the rest of the log is
            # the statement Lean actually proved.
            facts["lean_statement"] = log[m.end():].strip()
    return problems, facts


def write_lean(task: str, out_path: Path, schema: dict = LEAN_SCHEMA,
               prefix: str = "", forbidden: list[str] = ESCAPE_HATCHES,
               theorem_name=None, check=None) -> dict | None:
    """Ask for Lean code, compile + audit it, feed problems back; up to MAX_ATTEMPTS.

    The file compiled is `prefix + answer["lean"]` (prefix = pasted-in
    definitions), plus `#print axioms` / `#check` for the main theorem if
    `theorem_name(answer)` gives one; `check(answer)`, if given, returns
    further audit problems. Every attempt is kept as <name>.attemptN.lean /
    .log next to out_path. Returns the model's final
    answer (plus audit facts) if it passed, else None.
    """
    prompt = task
    offset = prefix.count("\n")
    for n in range(1, MAX_ATTEMPTS + 1):
        print(f"  attempt {n}:", end="")
        answer = call_claude(prompt, schema)
        theorem = theorem_name(answer) if theorem_name else None
        suffix = f"\n\n#print axioms {theorem}\n#check @{theorem}\n" if theorem else ""
        attempt = out_path.with_suffix(f".attempt{n}.lean")
        attempt.write_text(prefix + answer["lean"] + suffix)
        ok, log = compile_lean(attempt)
        log = shift_line_numbers(log, attempt.name, offset)
        problems, facts = audit(answer["lean"], log, forbidden, theorem)
        if check:
            problems += check(answer)
        if problems:
            log += "\n--- AUDIT ---\n" + "\n".join(f"audit: {p}" for p in problems) + "\n"
        attempt.with_suffix(".log").write_text(log)
        if ok and not problems:
            out_path.write_text(prefix + answer["lean"] + suffix)
            print(f"  passed -> {out_path.name}")
            return answer | facts | {"attempts": n}
        first = (problems or log.strip().splitlines() or ["(no output)"])[0]
        print(f"  failed: {first}")
        prompt = (task
                  + "\n\n--- YOUR PREVIOUS ATTEMPT ---\n" + answer["lean"]
                  + "\n\n--- LEAN OUTPUT AND AUDIT (line numbers count from your code) ---\n"
                  + log
                  + "\n\nFix every problem above and return your complete corrected code.")
    print(f"  gave up after {MAX_ATTEMPTS} attempts")
    return None


# --- Step 2a: shared definitions ---------------------------------------------

DEFS_SCHEMA = {
    "type": "object",
    "properties": {"lean": {"type": "string"}, "namespace": {"type": "string"},
                   "notes": {"type": "string"}},
    "required": ["lean", "namespace", "notes"],
}


def front_matter(paper: Path) -> str:
    """The paper's LaTeX up to its first \\section (title, authors, abstract)."""
    tex = paper.read_text()
    m = re.search(r"\\section\b", tex)
    return tex[:m.start()] if m else tex[:3000]


def check_namespace(answer: dict) -> list[str]:
    """Defs.lean must be wrapped in the paper-specific namespace it reports."""
    ns, bare = answer["namespace"], strip_comments(answer["lean"]).strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_']*", ns):
        return [f"namespace `{ns}` is not a single Lean identifier"]
    if not (re.match(rf"namespace {re.escape(ns)}\s", bare) and bare.endswith(f"end {ns}")):
        return [f"the code must begin with `namespace {ns}` and end with `end {ns}`"]
    return []


def paper_namespace(defs_lean: str) -> str:
    """The namespace Defs.lean is wrapped in (its first `namespace`, by check_namespace)."""
    return re.search(r"(?m)^namespace (\S+)", strip_comments(defs_lean)).group(1)


def defs(paper: Path, run_dir: Path) -> None:
    print(f"defs: {run_dir}/claims.json -> {run_dir}/Defs.lean")
    items = json.loads((run_dir / "claims.json").read_text())["items"]
    definitions = [i for i in items if i["kind"] == "definition"]
    task = ((PROMPTS / "defs.md").read_text()
            .replace("{front_matter}", front_matter(paper))
            .replace("{definitions}", json.dumps(definitions, indent=2)))
    answer = write_lean(task, run_dir / "Defs.lean", DEFS_SCHEMA, check=check_namespace)
    if answer:
        (run_dir / "Defs.notes.md").write_text(answer["notes"] + "\n")
        print("  notes:\n    " + answer["notes"].replace("\n", "\n    "))


# --- Step 2b: claims ---------------------------------------------------------

CLAIM_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"enum": ["proved", "disproved"]},
        "lean": {"type": "string"},
        "notes": {"type": "string"},
    },
    "required": ["verdict", "lean", "notes"],
}


def claims(run_dir: Path, only: str | None = None) -> None:
    items = json.loads((run_dir / "claims.json").read_text())["items"]
    # TODO: pasting Defs.lean into every claim file is the barebones option;
    # see TODO.org for doing this properly (olean + LEAN_PATH, or Lake).
    defs_lean = (run_dir / "Defs.lean").read_text().rstrip("\n") + "\n\n"
    ns = paper_namespace(defs_lean)
    out_dir = run_dir / "claims"
    out_dir.mkdir(exist_ok=True)
    results_path = run_dir / "results.json"
    results = json.loads(results_path.read_text()) if results_path.exists() else {}

    for item in items:
        if item["kind"] != "claim" or (only and item["id"] != only):
            continue
        print(f"claim {item['id']} ({item['label']}) -> claims/{item['id']}.lean")
        task = ((PROMPTS / "claim.md").read_text()
                .replace("{id}", item["id"])
                .replace("{namespace}", ns)
                .replace("{defs}", defs_lean)
                .replace("{claim}", json.dumps(item, indent=2, ensure_ascii=False)))
        cid = item["id"]
        answer = write_lean(
            task, out_dir / f"{cid}.lean", CLAIM_SCHEMA, defs_lean,
            forbidden=ESCAPE_HATCHES + NEW_DEFINITIONS,
            theorem_name=lambda a: f"{ns}.{cid}" if a["verdict"] == "proved"
                                   else f"{ns}.{cid}_false")
        if answer:
            results[cid] = {"outcome": answer["verdict"],
                            "attempts": answer["attempts"],
                            "lean_statement": answer["lean_statement"],
                            "axioms": answer["axioms"],
                            "notes": answer["notes"]}
            print(f"  => {answer['verdict'].upper()}")
        else:
            results[item["id"]] = {"outcome": "failed", "attempts": MAX_ATTEMPTS, "notes": ""}
            print("  => FAILED")
        results_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")

    print("\nsummary:")
    for cid, r in results.items():
        print(f"  {cid:8} {r['outcome']:10} ({r['attempts']} attempt(s))")


# --- CLI ---------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) not in (3, 4) or sys.argv[1] not in {"extract", "defs", "claims"}:
        sys.exit(__doc__)
    step, paper = sys.argv[1], Path(sys.argv[2])
    run_dir = RUNS / paper.parent.name
    run_dir.mkdir(parents=True, exist_ok=True)
    if step == "extract":
        extract(paper, run_dir)
    elif step == "defs":
        defs(paper, run_dir)
    elif step == "claims":
        claims(run_dir, sys.argv[3] if len(sys.argv) == 4 else None)


if __name__ == "__main__":
    main()
