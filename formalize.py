#!/usr/bin/env python3
"""Barebones auto-formalizer for semantics papers.

Usage:
    python3 formalize.py extract PAPER.tex            # -> claims.json
    python3 formalize.py defs    PAPER.tex            # -> Defs.lean
    python3 formalize.py state   PAPER.tex [claim-id] # -> statements.json
    python3 formalize.py prove   PAPER.tex [claim-id] # -> claims/<id>.lean, results.json

Review statements.json (edit or delete entries) before running `prove`:
the prover proves or refutes each statement exactly as written there.

Every step writes its output to the run directory: runs/<paper name>/ by
default (the folder's name if the file is called paper.tex, main.tex, ...),
or --out DIR. See README.md.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent
PROMPTS = ROOT / "prompts"
RUNS = ROOT / "runs"

SYSTEM_PROMPT = "You are a careful assistant. Follow the user's instructions exactly."


def call_claude(prompt: str, schema: dict) -> dict:
    """Send one prompt to `claude -p` (no tools) and return its JSON answer.

    Each call starts from a fresh, isolated context: run from an empty temp
    directory (no CLAUDE.md, auto-memory, git status, or repo path) with a
    minimal system prompt, no settings, MCP servers, or skills. The prompt is
    all the model knows.
    """
    cmd = [
        "claude", "-p",
        "--tools", "",                  # pure text-in/text-out, no file access
        "--no-session-persistence",
        "--system-prompt", SYSTEM_PROMPT,
        "--setting-sources", "",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--output-format", "json",
        "--json-schema", json.dumps(schema),
    ]
    with tempfile.TemporaryDirectory() as cwd:
        out = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                             check=True, cwd=cwd)
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
                    "kind": {"enum": ["definition", "example", "claim"]},
                    "label": {"type": "string"},
                    "latex": {"type": "string"},
                    "statement": {"type": "string"},
                    "analysis": {"type": "string"},
                    "depends_on": {"type": "array", "items": {"type": "string"}},
                    "cites": {"type": "array", "items": {"type": "string"}},
                    "concerns": {"type": "string"},
                },
                "required": ["id", "kind", "label", "latex", "statement", "analysis",
                             "depends_on", "cites", "concerns"],
            },
        }
    },
    "required": ["items"],
}


def locate(tex: str, latex: str) -> dict | None:
    """Where `latex` occurs verbatim in `tex` (up to whitespace): lines and section."""
    norm, pos = [], []                  # tex with whitespace runs collapsed, and
    for i, c in enumerate(tex):         # each kept character's offset in tex
        if c.isspace():
            if norm and norm[-1] == " ":
                continue
            c = " "
        norm.append(c)
        pos.append(i)
    needle = " ".join(latex.split())
    k = "".join(norm).find(needle) if needle else -1
    if k < 0:
        return None
    start, end = pos[k], pos[k + len(needle) - 1]
    sections = re.findall(r"\\(?:sub)*section\*?\{([^}]*)\}", tex[:start])
    return {"lines": [tex.count("\n", 0, start) + 1, tex.count("\n", 0, end) + 1],
            "section": sections[-1] if sections else None}


def extract(paper: Path, run_dir: Path) -> None:
    print(f"extract: {paper} -> {run_dir}/claims.json")
    tex = paper.read_text()
    result = call_claude((PROMPTS / "extract.md").read_text() + tex, CLAIMS_SCHEMA)
    kinds = {i["id"]: i["kind"] for i in result["items"]}
    seen = set()
    for item in result["items"]:
        # Located by us, not the model; not found means `latex` isn't verbatim.
        item["source"] = locate(tex, item["latex"])
        problems = [f"depends on unknown or later item {d}"
                    for d in item["depends_on"] if d not in seen]
        problems += [f"depends on claim {d} (belongs in cites)"
                     for d in item["depends_on"] if kinds.get(d) == "claim"]
        problems += [f"cites {c}, which is not a claim"
                     for c in item["cites"] if kinds.get(c) != "claim"]
        if item["id"] in seen:
            problems.append("duplicate id")
        if item["source"] is None:
            problems.append("latex not found verbatim in the paper")
        seen.add(item["id"])
        where = f"l.{item['source']['lines'][0]}" if item["source"] else "l.?"
        print(f"  {item['id']:16} {item['kind']:10} {where:6} {item['label']}")
        for flag in problems + ([item["concerns"]] if item["concerns"] else []):
            print(f"      ⚠ {flag}")
    (run_dir / "claims.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")


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
NEW_DEFINITIONS = [r"(?m)^\s*(?:@\[[^\]]*\]\s*)?(?:(?:private|protected|noncomputable|local|scoped)\s+)*"
                   r"(?:def|abbrev|structure|inductive|class|instance|opaque"
                   r"|notation|infix\w*|prefix|postfix|macro|syntax)\b"]
# The prover's code sits between a fixed statement's context and its theorem
# header, so it may not change how names or notation in that header resolve.
SCOPE_CHANGES = [r"(?m)^\s*(?:open|export|attribute|set_option|local|scoped"
                 r"|variable|universe|section|namespace|end)\b"]
# A statement is a single term: no commands or declarations around it.
COMMANDS = SCOPE_CHANGES + [r"(?m)^\s*(?:theorem|lemma|example|#\w+)\b"]


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
               theorem_name=None, check=None, assemble=None, own=None,
               stop=None) -> dict | None:
    """Ask for Lean code, compile + audit it, feed problems back; up to MAX_ATTEMPTS.

    The code is `answer["lean"]`, or `assemble(answer)` if given (the runner
    builds it from the answer's fields; `own(answer)` is then the part the
    model wrote, which is what `forbidden` is scanned for). The file compiled is `prefix + code`
    (prefix = pasted-in definitions), plus `#print axioms` / `#check` for the
    main theorem if `theorem_name(answer)` gives one; `check(answer)`, if
    given, returns further audit problems. If `stop(answer)`, the answer is
    returned as is, uncompiled. Every attempt is kept as <name>.attemptN.lean /
    .log next to out_path. Returns the model's final answer (plus audit facts)
    if it passed, else None.
    """
    prompt = task
    offset = prefix.count("\n")
    for n in range(1, MAX_ATTEMPTS + 1):
        print(f"  attempt {n}:", end="")
        answer = call_claude(prompt, schema)
        if stop and stop(answer):
            print("  stopped")
            return answer | {"attempts": n}
        code = assemble(answer) if assemble else answer["lean"]
        theorem = theorem_name(answer) if theorem_name else None
        suffix = f"\n\n#print axioms {theorem}\n#check @{theorem}\n" if theorem else ""
        attempt = out_path.with_suffix(f".attempt{n}.lean")
        attempt.write_text(prefix + code + suffix)
        ok, log = compile_lean(attempt)
        log = shift_line_numbers(log, attempt.name, offset)
        problems, facts = audit(own(answer) if own else code, log, forbidden, theorem)
        if check:
            problems += check(answer)
        if problems:
            log += "\n--- AUDIT ---\n" + "\n".join(f"audit: {p}" for p in problems) + "\n"
        attempt.with_suffix(".log").write_text(log)
        if ok and not problems:
            out_path.write_text(prefix + code + suffix)
            print(f"  passed -> {out_path.name}")
            return answer | facts | {"attempts": n}
        # A compile error also shows up as sorryAx in the audit; report the cause.
        first = ((log.strip().splitlines() if not ok else []) or problems or ["(no output)"])[0]
        print(f"  failed: {first}")
        prompt = (task
                  + "\n\n--- YOUR PREVIOUS ATTEMPT (as compiled, after DEFINITIONS) ---\n" + code
                  + "\n\n--- LEAN OUTPUT AND AUDIT (line numbers count from the code above) ---\n"
                  + log
                  + "\n\nFix every problem above and return your complete corrected code.")
    print(f"  gave up after {MAX_ATTEMPTS} attempts")
    return None


BULKY = ("defs", "claim", "statement", "front_matter", "definitions", "examples")


def fill(template: str, **fields: str) -> str:
    """Fill {field} placeholders; the bulky ones (defs, claim) go in last."""
    for key in sorted(fields, key=lambda k: k in BULKY):
        template = template.replace("{" + key + "}", fields[key])
    return template


# --- Step 2: shared definitions ----------------------------------------------

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


def check_examples(ids: list[str]):
    """Defs.lean must define each example under the example's own id."""
    def check(answer: dict) -> list[str]:
        bare = strip_comments(answer["lean"])
        return [f"no definition named `{i}` (example {i})" for i in ids
                if not re.search(rf"(?m)^\s*(?:@\[[^\]]*\]\s*)?(?:noncomputable\s+)?"
                                 rf"(?:def|abbrev)\s+{re.escape(i)}\b", bare)]
    return check


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
    examples = [i for i in items if i["kind"] == "example"]
    task = fill((PROMPTS / "defs.md").read_text(), front_matter=front_matter(paper),
                definitions=json.dumps(definitions, indent=2, ensure_ascii=False),
                examples=json.dumps(examples, indent=2, ensure_ascii=False))
    has_examples = check_examples([e["id"] for e in examples])
    answer = write_lean(task, run_dir / "Defs.lean", DEFS_SCHEMA,
                        check=lambda a: check_namespace(a) + has_examples(a))
    if answer:
        (run_dir / "Defs.notes.md").write_text(answer["notes"] + "\n")
        print("  notes:\n    " + answer["notes"].replace("\n", "\n    "))


# --- Step 3: state claims ---------------------------------------------------

STATE_SCHEMA = {
    "type": "object",
    "properties": {"statement": {"type": "string"}, "notes": {"type": "string"}},
    "required": ["statement", "notes"],
}


def claim_items(run_dir: Path, only: str | None) -> list[dict]:
    items = json.loads((run_dir / "claims.json").read_text())["items"]
    return [i for i in items if i["kind"] == "claim" and (not only or i["id"] == only)]


def load_defs(run_dir: Path) -> tuple[str, str]:
    """Defs.lean (to paste in as a prefix) and its namespace."""
    # TODO: pasting Defs.lean into every claim file is the barebones option;
    # see TODO.org for doing this properly (olean + LEAN_PATH, or Lake).
    defs_lean = (run_dir / "Defs.lean").read_text().rstrip("\n") + "\n\n"
    return defs_lean, paper_namespace(defs_lean)


def state(run_dir: Path, only: str | None = None) -> None:
    defs_lean, ns = load_defs(run_dir)
    out_dir = run_dir / "statements"
    out_dir.mkdir(exist_ok=True)
    path = run_dir / "statements.json"
    statements = json.loads(path.read_text()) if path.exists() else {}

    for item in claim_items(run_dir, only):
        cid = item["id"]
        print(f"state {cid} ({item['label']}) -> statements.json")
        task = fill((PROMPTS / "state.md").read_text(), namespace=ns, defs=defs_lean,
                    claim=json.dumps(item, indent=2, ensure_ascii=False))
        answer = write_lean(
            task, out_dir / f"{cid}.lean", STATE_SCHEMA, defs_lean,
            forbidden=ESCAPE_HATCHES + NEW_DEFINITIONS + COMMANDS,
            assemble=lambda a: (f"namespace {ns}\n\nexample : Prop :=\n"
                                f"  {a['statement'].strip()}\n\nend {ns}\n"),
            own=lambda a: a["statement"])
        if answer:
            statements[cid] = {"statement": answer["statement"].strip(),
                               "attempts": answer["attempts"], "notes": answer["notes"]}
            print(f"  => {statements[cid]['statement']}")
        else:
            statements.pop(cid, None)
            print("  => FAILED (no statement)")
        path.write_text(json.dumps(statements, indent=2, ensure_ascii=False) + "\n")
    print(f"\nreview {path} before running `prove`")


# --- Step 4: prove / refute ---------------------------------------------------

PROVE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"enum": ["proved", "disproved", "challenge"]},
        "helpers": {"type": "string"},
        "proof": {"type": "string"},
        "notes": {"type": "string"},
    },
    "required": ["verdict", "helpers", "proof", "notes"],
}


def prove(run_dir: Path, only: str | None = None) -> None:
    defs_lean, ns = load_defs(run_dir)
    statements = json.loads((run_dir / "statements.json").read_text())
    out_dir = run_dir / "claims"
    out_dir.mkdir(exist_ok=True)
    results_path = run_dir / "results.json"
    results = json.loads(results_path.read_text()) if results_path.exists() else {}

    for item in claim_items(run_dir, only):
        cid = item["id"]
        if cid not in statements:
            print(f"prove {cid}: skipped, no statement in statements.json (run `state`)")
            continue
        stmt = statements[cid]["statement"]
        print(f"prove {cid} ({item['label']}) -> claims/{cid}.lean")
        task = fill((PROMPTS / "prove.md").read_text(), id=cid, namespace=ns,
                    defs=defs_lean, statement=stmt,
                    claim=json.dumps(item, indent=2, ensure_ascii=False))

        # The theorem header is ours, built from the frozen statement; the
        # model only supplies helpers and the proof term.
        def assemble(a: dict) -> str:
            header = (f"theorem {cid} :\n    {stmt} :=" if a["verdict"] == "proved"
                      else f"theorem {cid}_false :\n    ¬ ({stmt}) :=")
            helpers = a["helpers"].strip()
            return (f"namespace {ns}\n\n" + (helpers + "\n\n" if helpers else "")
                    + f"{header} {a['proof'].strip()}\n\nend {ns}\n")

        answer = write_lean(
            task, out_dir / f"{cid}.lean", PROVE_SCHEMA, defs_lean,
            forbidden=ESCAPE_HATCHES + NEW_DEFINITIONS + SCOPE_CHANGES,
            assemble=assemble, own=lambda a: a["helpers"] + "\n" + a["proof"],
            stop=lambda a: a["verdict"] == "challenge",
            theorem_name=lambda a: f"{ns}.{cid}" if a["verdict"] == "proved"
                                   else f"{ns}.{cid}_false")
        if answer and answer["verdict"] == "challenge":
            results[cid] = {"outcome": "challenged", "attempts": answer["attempts"],
                            "statement": stmt, "notes": answer["notes"]}
            print(f"  => CHALLENGED: {answer['notes']}")
        elif answer:
            results[cid] = {"outcome": answer["verdict"],
                            "attempts": answer["attempts"],
                            "statement": stmt,
                            "lean_statement": answer["lean_statement"],
                            "axioms": answer["axioms"],
                            "notes": answer["notes"]}
            print(f"  => {answer['verdict'].upper()}")
        else:
            results[cid] = {"outcome": "open", "attempts": MAX_ATTEMPTS,
                            "statement": stmt, "notes": ""}
            print("  => OPEN")
        results_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")

    print("\nsummary:")
    for cid, r in results.items():
        print(f"  {cid:8} {r['outcome']:10} ({r['attempts']} attempt(s))")


# --- CLI ---------------------------------------------------------------------

# File names that say nothing about the paper; their run is named after the folder.
GENERIC_STEMS = {"paper", "main", "article", "manuscript", "draft"}


def run_dir_for(paper: Path, out: str | None) -> Path:
    """The run directory for `paper`, refusing one that belongs to another paper."""
    if out:
        run_dir = Path(out)
    else:
        name = paper.stem
        if name.lower() in GENERIC_STEMS:
            name = paper.resolve().parent.name
        run_dir = RUNS / name
    run_dir.mkdir(parents=True, exist_ok=True)
    marker, source = run_dir / "paper.path", str(paper.resolve())
    if marker.exists() and marker.read_text().strip() != source:
        sys.exit(f"{run_dir} holds the run for {marker.read_text().strip()},\n"
                 f"not {source}. Use --out DIR to choose another run directory.")
    marker.write_text(source + "\n")
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Formalize a semantics paper in Lean, one step at a time.",
        epilog="Steps, in order: extract, defs, state, prove. "
               "Review statements.json before running prove.")
    parser.add_argument("step", choices=["extract", "defs", "state", "prove"])
    parser.add_argument("paper", type=Path, help="the paper's LaTeX source (one .tex file)")
    parser.add_argument("claim", nargs="?",
                        help="state/prove: only this claim id (default: all claims)")
    parser.add_argument("--out", metavar="DIR",
                        help="run directory (default: runs/<paper name>)")
    args = parser.parse_args()
    if not args.paper.is_file():
        parser.error(f"no such file: {args.paper}")
    if args.claim and args.step in ("extract", "defs"):
        parser.error(f"{args.step} takes no claim id")
    run_dir = run_dir_for(args.paper, args.out)
    print(f"run directory: {run_dir}")
    if args.step == "extract":
        extract(args.paper, run_dir)
    elif args.step == "defs":
        defs(args.paper, run_dir)
    elif args.step == "state":
        state(run_dir, args.claim)
    elif args.step == "prove":
        prove(run_dir, args.claim)


if __name__ == "__main__":
    main()
