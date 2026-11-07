#!/usr/bin/env python3
"""Sinnmaschine: a barebones auto-formalizer for semantics papers.

Usage:
    python3 formalize.py extract PAPER.tex            # -> claims.json
    python3 formalize.py defs    PAPER.tex            # -> Defs.lean
    python3 formalize.py state   PAPER.tex [claim-id] # -> statements.json
    python3 formalize.py backtranslate PAPER.tex [claim-id] # -> backtranslations.json
    python3 formalize.py prove   PAPER.tex [claim-id] # -> claims/<id>.lean, results.json

Review statements.json (edit or delete entries) before running `prove`:
the prover proves or refutes each statement exactly as written there.

Every step writes its output to the run directory: runs/<paper name>/ by
default (the folder's name if the file is called paper.tex, main.tex, ...),
or --out DIR. See README.md.
"""

import argparse
import datetime
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).parent
PROMPTS = ROOT / "prompts"
RUNS = ROOT / "runs"

SYSTEM_PROMPT = "You are a careful assistant. Follow the instructions exactly."

SPENT = []   # the cost of each model call in this run, in USD

_OUTPUT = threading.local()   # .buf: where `say` writes in this thread, if set


def say(*args, **kwargs) -> None:
    """`print`, but into this thread's buffer when running under `buffered`."""
    print(*args, file=getattr(_OUTPUT, "buf", None) or sys.stdout, **kwargs)


def buffered(fn, *args):
    """Run fn(*args), collecting what it `say`s. Returns (output, fn's result)."""
    _OUTPUT.buf = io.StringIO()
    try:
        result = fn(*args)
        return _OUTPUT.buf.getvalue(), result
    finally:
        _OUTPUT.buf = None


def call_claude(prompt: str, schema: dict, shared_until: str | None = None,
                model: str | None = None, effort: str | None = None) -> dict:
    """Send one prompt to `claude -p` (no tools) and return its JSON answer.

    Each call starts from a fresh, isolated context: run from an empty temp
    directory (no CLAUDE.md, auto-memory, git status, or repo path) with a
    minimal system prompt, no settings, MCP servers, or skills. The prompt is
    all the model knows.

    Caching. Claude Code caches a prompt up to the end of the user message,
    which differs from call to call, so a cached prompt is never read back
    and its cache write costs more than no caching at all. With
    `shared_until`, the prompt is split before that marker: the part before
    it (instructions, definitions, the paper), the same for every claim in a
    step, goes in the system prompt, which is cached for 5 minutes and read
    back at a tenth of the price by the next claim; the rest is the user
    message. Without it, caching is off.

    `model` is a `--model` alias (e.g. "sonnet"), `effort` an `--effort`
    level (low … max); None = the CLI's default.
    """
    system, user = SYSTEM_PROMPT, prompt
    if shared_until and shared_until in prompt:
        i = prompt.index(shared_until)
        system, user = SYSTEM_PROMPT + "\n\n" + prompt[:i].rstrip(), prompt[i:]
        env = os.environ | {"FORCE_PROMPT_CACHING_5M": "1"}
    else:
        env = os.environ | {"DISABLE_PROMPT_CACHING": "1"}
    cmd = [
        "claude", "-p",
        "--tools", "",                  # pure text-in/text-out, no file access
        "--no-session-persistence",
        "--system-prompt", system,
        "--setting-sources", "",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--output-format", "json",
        "--json-schema", json.dumps(schema),
    ] + (["--model", model] if model else []) + (["--effort", effort] if effort else [])
    with tempfile.TemporaryDirectory() as cwd:
        out = subprocess.run(cmd, input=user, capture_output=True, text=True,
                             check=True, cwd=cwd, env=env)
    reply = json.loads(out.stdout)
    if reply.get("is_error"):
        sys.exit(f"claude returned an error: {reply.get('result')}")
    SPENT.append(reply["total_cost_usd"])
    u = reply["usage"]
    say(f"  (cost ${reply['total_cost_usd']:.3f}, {reply['duration_ms'] / 1000:.0f}s;"
          f" tokens: {u['cache_read_input_tokens']} cached,"
          f" {u['cache_creation_input_tokens'] + u['input_tokens']} new,"
          f" {u['output_tokens']} out)")
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


def find_span(tex: str, latex: str) -> tuple[int, int] | None:
    """Character offsets [start, end) of `latex` in `tex`, matching up to whitespace."""
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
    return pos[k], pos[k + len(needle) - 1] + 1


def locate(tex: str, latex: str) -> dict | None:
    """Where `latex` occurs verbatim in `tex` (up to whitespace): lines and section."""
    span = find_span(tex, latex)
    if span is None:
        return None
    start, end = span
    sections = [braced(tex, m.end()) for m in
                re.finditer(r"\\(?:sub)*section\*?(?:\[[^\]]*\])?\{", tex[:start])]
    return {"lines": [tex.count("\n", 0, start) + 1, tex.count("\n", 0, end - 1) + 1],
            "section": " ".join(sections[-1].split()) if sections else None}


def braced(tex: str, i: int) -> str:
    """The text from `i` up to the `}` that closes the `{` just before it."""
    depth, j = 1, i
    while j < len(tex) and depth:
        depth += {"{": 1, "}": -1}.get(tex[j], 0)
        j += 1
    return tex[i:j - 1]


def env_body(env: str) -> str:
    """An environment's content without `\\begin{…}[…]`, labels and `\\end{…}`, whitespace-normalized."""
    body = re.sub(r"^\\begin\{\w+\*?\}(\[[^\]]*\])?", "", env.strip())
    body = re.sub(r"\\end\{\w+\*?\}$", "", body.strip())
    return " ".join(re.sub(r"\\label\{[^}]*\}", "", body).split())


THEOREM_LIKE = {"definition", "theorem", "proposition", "lemma", "corollary", "fact",
                "claim", "conjecture", "observation", "prediction", "generalization",
                "hypothesis", "principle", "assumption", "remark"}


def whole_environment(tex: str, latex: str) -> str | None:
    """If `latex` is part of a theorem-like environment but not all of it, the whole one.

    Extraction sometimes copies one line of a definition; the comparison
    and the review need the item as the paper states it.
    """
    span = find_span(tex, latex)
    if span is None:
        return None
    names = THEOREM_LIKE | set(re.findall(r"\\newtheorem\*?\{(\w+)\}", tex))
    for begin in re.finditer(r"\\begin\{(\w+)\*?\}", tex[:span[0] + 1]):
        if begin.group(1) not in names:
            continue
        end = tex.find(f"\\end{{{begin.group(1)}", begin.end())
        end = tex.find("}", end) + 1 if end >= 0 else -1
        if begin.start() <= span[0] and span[1] <= end:
            whole = tex[begin.start():end]
            return whole if " ".join(whole.split()) != " ".join(latex.split()) else None
    return None


# --- Claim ids -----------------------------------------------------------------

# Ids come from the model and end up in file names and Lean declarations, so
# they're held to a safe alphabet: no path separators, dots, spaces or
# guillemets. In Lean they're always written «id», which allows hyphens and
# keywords.
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


def check_id(cid: str) -> str:
    if not ID_RE.fullmatch(cid):
        sys.exit(f"unsafe item id {cid!r}: ids may only use letters, digits, - and _"
                 " (fix it in claims.json, with every reference to it)")
    return cid


def safe_ids(items: list[dict]) -> dict[str, str]:
    """Rename ids outside ID_RE, references included. Returns {old: new} for the renamed."""
    taken = {i["id"] for i in items if ID_RE.fullmatch(i["id"])}
    renamed = {}
    for item in items:
        old = item["id"]
        if ID_RE.fullmatch(old) or old in renamed:
            continue
        base = re.sub(r"[^A-Za-z0-9_-]", "_", old).lstrip("_-")[:60] or "item"
        new, n = base, 2
        while new in taken:
            new, n = f"{base}_{n}", n + 1
        taken.add(new)
        renamed[old] = new
    for item in items:
        item["id"] = renamed.get(item["id"], item["id"])
        item["depends_on"] = [renamed.get(d, d) for d in item["depends_on"]]
        item["cites"] = [renamed.get(c, c) for c in item["cites"]]
    return renamed


def id_path(directory: Path, cid: str, suffix: str) -> Path:
    """<directory>/<cid><suffix>, refusing an unsafe id or a path outside directory."""
    path = directory / f"{check_id(cid)}{suffix}"
    if not path.resolve().is_relative_to(directory.resolve()):
        sys.exit(f"refusing to write outside {directory}: {path}")
    return path


def lean_id(cid: str) -> str:
    """A claim id as a Lean identifier."""
    return f"«{check_id(cid)}»"


def extract(paper: Path, run_dir: Path) -> None:
    print(f"extract: {paper} -> {run_dir}/claims.json")
    tex = paper.read_text()
    result = call_claude((PROMPTS / "extract.md").read_text() + tex, CLAIMS_SCHEMA)
    for old, new in safe_ids(result["items"]).items():
        print(f"  ⚠ unsafe id {old!r} renamed to {new!r}")
    kinds = {i["id"]: i["kind"] for i in result["items"]}
    seen = set()
    for item in result["items"]:
        # Located by us, not the model; not found means `latex` isn't verbatim.
        item_latex = item["latex"]
        expanded = whole_environment(tex, item_latex)
        if expanded:
            item["latex"] = expanded
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
        if expanded and env_body(expanded) != " ".join(item_latex.split()):
            problems.append("latex was only part of its environment: expanded to the whole")
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
    """Remove Lean comments, docstrings included: `-- …` and nested `/- … -/`.

    String and character literals are kept whole, so a `--` inside one doesn't
    start a comment.
    """
    out, i, n = [], 0, len(code)
    while i < n:
        if code.startswith("/-", i):
            depth, i = 1, i + 2
            while i < n and depth:
                if code.startswith("/-", i):
                    depth, i = depth + 1, i + 2
                elif code.startswith("-/", i):
                    depth, i = depth - 1, i + 2
                else:
                    i += 1
            out.append(" ")
        elif code.startswith("--", i):
            while i < n and code[i] != "\n":
                i += 1
        elif code[i] == '"' or (code[i] == "'" and re.match(r"'(\\.|[^\\'])'", code[i:i + 4])):
            quote, j = code[i], i + 1
            while j < n and code[j] != quote:
                j += 2 if code[j] == "\\" else 1
            out.append(code[i:j + 1])
            i = j + 1
        else:
            out.append(code[i])
            i += 1
    return "".join(out)


def audit(code: str, log: str, forbidden: list[str],
          theorem: str | None) -> tuple[list[str], dict]:
    """Check the model's code and Lean's output. Returns (problems, facts)."""
    problems, facts = [], {}
    bare = strip_comments(code)
    for pattern in forbidden:
        for m in re.finditer(pattern, bare):
            problems.append(f"forbidden construct `{m.group(0).strip()}` in your code")
    if theorem:
        # Lean prints «x» as plain x where x is a valid identifier, so the
        # guillemets are optional in the match.
        name = r"\.".join(f"«?{re.escape(part.strip('«»'))}»?"
                          for part in re.split(r"\.(?![^«]*»)", theorem))
        m = re.search(rf"^'{name}' (?:depends on axioms: \[(.*)\]"
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
               stop=None, shared_until=None, model=None, effort=None,
               attempts=MAX_ATTEMPTS, start=1) -> dict | None:
    """Ask for Lean code, compile + audit it, feed problems back; up to `attempts` times.

    The code is `answer["lean"]`, or `assemble(answer)` if given (the runner
    builds it from the answer's fields; `own(answer)` is then the part the
    model wrote, which is what `forbidden` is scanned for). The file compiled is `prefix + code`
    (prefix = pasted-in definitions), plus `#print axioms` / `#check` for the
    main theorem if `theorem_name(answer)` gives one; `check(answer)`, if
    given, returns further audit problems. If `stop(answer)`, the answer is
    returned as is, uncompiled. `shared_until` is passed to `call_claude`
    (the task up to it is cached across claims and attempts), `model` and
    `effort` to it as is. Every attempt is kept as <name>.attemptN.lean / .log next to
    out_path, N counting from `start` (so a second round doesn't overwrite
    the first). Returns the model's final answer (plus audit facts)
    if it passed, else None.
    """
    prompt = task
    offset = prefix.count("\n")
    for n in range(start, start + attempts):
        label = ", ".join(x for x in (model, effort) if x)
        say(f"  attempt {n}" + (f" ({label})" if label else "") + ":", end="")
        answer = call_claude(prompt, schema, shared_until, model, effort)
        if stop and stop(answer):
            say("  stopped")
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
            say(f"  passed -> {out_path.name}")
            return answer | facts | {"attempts": n}
        # A compile error also shows up as sorryAx in the audit; report the cause.
        first = ((log.strip().splitlines() if not ok else []) or problems or ["(no output)"])[0]
        say(f"  failed: {first}")
        prompt = (task
                  + "\n\n--- YOUR PREVIOUS ATTEMPT (as compiled, after DEFINITIONS) ---\n" + code
                  + "\n\n--- LEAN OUTPUT AND AUDIT (line numbers count from the code above) ---\n"
                  + log
                  + "\n\nFix every problem above and return your complete corrected code.")
    say(f"  gave up after {attempts} attempt(s)")
    return None


BULKY = ("defs", "claim", "statement", "front_matter", "definitions", "examples",
         "surface", "unfolded", "paper")


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


def claim_items(run_dir: Path, only: list[str] | None) -> list[dict]:
    """The claims in claims.json (only those named in `only`, if given)."""
    items = json.loads((run_dir / "claims.json").read_text())["items"]
    for i in items:
        check_id(i["id"])
    claims = [i for i in items if i["kind"] == "claim"]
    if only:
        unknown = set(only) - {i["id"] for i in claims}
        if unknown:
            sys.exit(f"no such claim in claims.json: {', '.join(sorted(unknown))}")
        claims = [i for i in claims if i["id"] in only]
    return claims


def load_defs(run_dir: Path) -> tuple[str, str]:
    """Defs.lean (to paste in as a prefix) and its namespace."""
    # TODO: pasting Defs.lean into every claim file is the barebones option;
    # see TODO.org for doing this properly (olean + LEAN_PATH, or Lake).
    defs_lean = (run_dir / "Defs.lean").read_text().rstrip("\n") + "\n\n"
    return defs_lean, paper_namespace(defs_lean)


def state(run_dir: Path, only: list[str] | None = None) -> None:
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
            task, id_path(out_dir, cid, ".lean"), STATE_SCHEMA, defs_lean,
            forbidden=ESCAPE_HATCHES + NEW_DEFINITIONS + COMMANDS,
            assemble=lambda a: (f"namespace {ns}\n\nexample : Prop :=\n"
                                f"  {a['statement'].strip()}\n\nend {ns}\n"),
            own=lambda a: a["statement"], shared_until="--- CLAIM ---")
        if answer:
            statements[cid] = {"statement": answer["statement"].strip(),
                               "attempts": answer["attempts"], "notes": answer["notes"]}
            print(f"  => {statements[cid]['statement']}")
        else:
            statements.pop(cid, None)
            print("  => FAILED (no statement)")
        path.write_text(json.dumps(statements, indent=2, ensure_ascii=False) + "\n")
    print(f"\nreview {path} before running `prove`")


# --- Step 3b: blind back-translation ------------------------------------------

BACK_SCHEMA = {
    "type": "object",
    "properties": {"surface": {"type": "string"}, "unfolded": {"type": "string"}},
    "required": ["surface", "unfolded"],
}

COMPARE_SCHEMA = {
    "type": "object",
    "properties": {
        "differences": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "reading": {"enum": ["surface", "unfolded"]},
                    "class": {"enum": ["substantive", "choice", "wording"]},
                    "description": {"type": "string"},
                    "model": {"type": "string"},
                },
                "required": ["reading", "class", "description", "model"],
            },
        },
    },
    "required": ["differences"],
}

NEUTRAL_NAMESPACE = "Paper"


def blind_defs(defs_lean: str) -> str:
    """Defs.lean as the translator may see it.

    Comments and docstrings are stripped (they cite the paper), and the
    namespace, which is named after the paper, is renamed to a neutral one.
    """
    ns = paper_namespace(defs_lean)
    bare = re.sub(rf"\b{re.escape(ns)}\b", NEUTRAL_NAMESPACE, strip_comments(defs_lean))
    return re.sub(r"\n\s*\n+", "\n\n", "\n".join(l.rstrip() for l in bare.splitlines())).strip()


def translator_prompt(defs_lean: str, statement: str) -> str:
    """The translator's whole input: stripped Lean and the bare statement.

    Built here, from these two arguments only, so that nothing else (the
    paper, claim ids, notes) can reach it.
    """
    return fill((PROMPTS / "backtranslate.md").read_text(),
                defs=blind_defs(defs_lean), statement=strip_comments(statement).strip())


def backtranslate(paper: Path, run_dir: Path, only: list[str] | None = None) -> None:
    """Blind back-translation of each statement, compared with the paper.

    The translator sees only stripped Lean (`translator_prompt`). The
    comparer sees the readings next to the claim and the whole paper, so it
    has the paper's own definitions, examples and translations, however
    well or badly extraction copied them.
    """
    defs_lean = (run_dir / "Defs.lean").read_text()
    statements = json.loads((run_dir / "statements.json").read_text())
    tex = paper.read_text()
    out_dir = run_dir / "backtranslations"
    out_dir.mkdir(exist_ok=True)
    path = run_dir / "backtranslations.json"
    results = json.loads(path.read_text()) if path.exists() else {}

    for item in claim_items(run_dir, only):
        cid = item["id"]
        if cid not in statements:
            print(f"skip {cid}: no statement (run `state`)")
            continue
        statement = statements[cid]["statement"]
        print(f"back-translate {cid} ({item['label']})")
        prompt = translator_prompt(defs_lean, statement)
        id_path(out_dir, cid, ".prompt.md").write_text(prompt)   # kept for auditing isolation
        reading = call_claude(prompt, BACK_SCHEMA, "--- STATEMENT ---")
        print(f"compare {cid}")
        diffs = call_claude(fill((PROMPTS / "compare.md").read_text(),
                                 claim=item["latex"], paper=tex,
                                 surface=reading["surface"], unfolded=reading["unfolded"]),
                            COMPARE_SCHEMA, "--- CLAIM ---")["differences"]
        flagged = any(d["class"] == "substantive" for d in diffs)
        results[cid] = {"statement": statement, **reading, "differences": diffs,
                        "flagged": flagged}
        for d in diffs:
            print(f"  {d['class']:11} ({d['reading']}) {d['description']}")
        print(f"  => {'FLAGGED' if flagged else 'no substantive difference'}")
        path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")

    print("\nsummary:")
    for cid, r in results.items():
        counts = {c: sum(d["class"] == c for d in r["differences"])
                  for c in ("substantive", "choice", "wording")}
        print(f"  {cid:16} {'FLAGGED' if r['flagged'] else 'ok':8} "
              + ", ".join(f"{n} {c}" for c, n in counts.items() if n))


# --- Step 3c: approve statements ----------------------------------------------

# decisions.json holds the user's rulings; `prove` reads it to refuse
# statements nobody approved. An approval names the statement by its hash, so
# editing an approved statement in statements.json voids the approval.

def statement_hash(statement: str) -> str:
    return hashlib.sha256(statement.encode()).hexdigest()


def load_decisions(run_dir: Path) -> dict:
    path = run_dir / "decisions.json"
    return json.loads(path.read_text()) if path.exists() else {"statements": {}}


def load_backtranslations(run_dir: Path) -> dict:
    path = run_dir / "backtranslations.json"
    return json.loads(path.read_text()) if path.exists() else {}


def backtranslation_issue(backs: dict, cid: str, stmt: str) -> str | None:
    """Why the back-translation doesn't vouch for `stmt`, or None if it does."""
    bt = backs.get(cid)
    if not bt:
        return "not back-translated"
    if bt["statement"] != stmt:
        return "back-translated from an older statement"
    if bt["flagged"]:
        return "back-translation flagged a substantive difference"
    return None


def approve(run_dir: Path, only: list[str] | None = None, override: bool = False) -> None:
    """Record the user's approval of each statement (default: every stated claim)."""
    statements = json.loads((run_dir / "statements.json").read_text())
    backs = load_backtranslations(run_dir)
    decisions = load_decisions(run_dir)
    for item in claim_items(run_dir, only):
        cid = item["id"]
        if cid not in statements:
            if only:
                print(f"approve {cid}: skipped, no statement (run `state`)")
            continue
        stmt = statements[cid]["statement"]
        issue = backtranslation_issue(backs, cid, stmt)
        if issue and not override:
            print(f"approve {cid}: refused, {issue} (run `backtranslate`,"
                  " or pass --override once you've reviewed it anyway)")
            continue
        decisions["statements"][cid] = {
            "decision": "approved", "by": "user",
            "date": datetime.date.today().isoformat(),
            "statement_sha256": statement_hash(stmt),
            "override": issue}
        print(f"approve {cid}" + (f" (despite: {issue})" if issue else ""))
    (run_dir / "decisions.json").write_text(
        json.dumps(decisions, indent=2, ensure_ascii=False) + "\n")


def approval_problem(decisions: dict, backs: dict, cid: str, stmt: str) -> str | None:
    """Why `prove` may not take `stmt` as approved, or None if it may."""
    d = decisions["statements"].get(cid)
    if not d or d["decision"] != "approved":
        return "not approved (run `approve`)"
    if d["statement_sha256"] != statement_hash(stmt):
        return "statement changed since it was approved"
    issue = backtranslation_issue(backs, cid, stmt)
    if issue and issue != d["override"]:
        return f"{issue} since it was approved"
    return None


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


# Proofs tried on every statement before any model call. Many denotation
# claims hold by evaluation alone; a statement closed this way costs nothing.
FIXED_PROOFS = ["by intros; rfl"]

# Who tries to prove, in order: (model, effort, attempts). A proof can't be
# wrong — Lean and the audit check it against the frozen statement — so a
# cheaper model or lower effort first only risks failing, and failures go up
# a tier. A `challenge` (the statement isn't faithful) is a judgment, not
# checked by Lean, so it goes up a tier too; only the last tier's challenge
# stands. None = the CLI's default.
# (Sonnet at "low" effort was tried on the real paper: no cheaper overall,
# one claim used 8x the output tokens, another needed the next tier.)
PROVE_TIERS = [("sonnet", None, 2), (None, None, 3)]

# Claims proved at once, once the first model call has written the cache.
PROVE_JOBS = 6


def try_fixed_proofs(prefix: str, assemble, out_path: Path,
                     theorem: str) -> tuple[str, dict] | None:
    """Try FIXED_PROOFS on the statement, no model. Returns (proof, audit facts) or None."""
    suffix = f"\n\n#print axioms {theorem}\n#check @{theorem}\n"
    for proof in FIXED_PROOFS:
        code = assemble({"verdict": "proved", "helpers": "", "proof": proof})
        attempt = out_path.with_suffix(".fixed.lean")
        attempt.write_text(prefix + code + suffix)
        ok, log = compile_lean(attempt)
        problems, facts = audit("", log, [], theorem)
        attempt.unlink()
        if ok and not problems:
            out_path.write_text(prefix + code + suffix)
            return proof, facts
    return None


def prove_one(item: dict, stmt: str, defs_lean: str, ns: str, out_dir: Path) -> dict:
    """Settle one frozen statement: fixed proofs, then the model tiers. Returns its result."""
    cid = item["id"]
    say(f"prove {cid} ({item['label']}) -> claims/{cid}.lean")
    task = fill((PROMPTS / "prove.md").read_text(), namespace=ns,
                defs=defs_lean, statement=stmt,
                claim=json.dumps(item, indent=2, ensure_ascii=False))

    # The theorem header is ours, built from the frozen statement; the
    # model only supplies helpers and the proof term.
    def assemble(a: dict) -> str:
        header = (f"theorem {lean_id(cid)} :\n    {stmt} :=" if a["verdict"] == "proved"
                  else f"theorem {lean_id(cid + '_false')} :\n    ¬ ({stmt}) :=")
        helpers = a["helpers"].strip()
        return (f"namespace {ns}\n\n" + (helpers + "\n\n" if helpers else "")
                + f"{header} {a['proof'].strip()}\n\nend {ns}\n")

    out_path = id_path(out_dir, cid, ".lean")
    fixed = try_fixed_proofs(defs_lean, assemble, out_path, f"{ns}.{lean_id(cid)}")
    if fixed:
        proof, facts = fixed
        say(f"  fixed proof `{proof}` passed -> {cid}.lean\n  => PROVED")
        return {"outcome": "proved", "attempts": 0, "model": None,
                "statement": stmt,
                "lean_statement": facts["lean_statement"],
                "axioms": facts["axioms"],
                "notes": f"Closed by the fixed proof `{proof}`, no model call."}

    answer, start = None, 1
    for model, effort, attempts in PROVE_TIERS:
        answer = write_lean(
            task, out_path, PROVE_SCHEMA, defs_lean,
            forbidden=ESCAPE_HATCHES + NEW_DEFINITIONS + SCOPE_CHANGES,
            assemble=assemble, own=lambda a: a["helpers"] + "\n" + a["proof"],
            stop=lambda a: a["verdict"] == "challenge", shared_until="--- CLAIM ---",
            theorem_name=lambda a: f"{ns}.{lean_id(cid)}" if a["verdict"] == "proved"
                                   else f"{ns}.{lean_id(cid + '_false')}",
            model=model, effort=effort, attempts=attempts, start=start)
        start = answer["attempts"] + 1 if answer else start + attempts
        if answer and answer["verdict"] != "challenge":
            break
    if answer and answer["verdict"] == "challenge":
        say(f"  => CHALLENGED: {answer['notes']}")
        return {"outcome": "challenged", "attempts": answer["attempts"],
                "model": model, "statement": stmt, "notes": answer["notes"]}
    if answer:
        say(f"  => {answer['verdict'].upper()}")
        return {"outcome": answer["verdict"],
                "attempts": answer["attempts"],
                "model": model,
                "statement": stmt,
                "lean_statement": answer["lean_statement"],
                "axioms": answer["axioms"],
                "notes": answer["notes"]}
    say("  => OPEN")
    return {"outcome": "open", "attempts": start - 1, "statement": stmt, "notes": ""}


def prove(run_dir: Path, only: list[str] | None = None, jobs: int = PROVE_JOBS,
          unreviewed: bool = False) -> None:
    """Prove or refute each approved statement; with `unreviewed`, every statement,
    and those not approved are marked unreviewed in results.json."""
    defs_lean, ns = load_defs(run_dir)
    statements = json.loads((run_dir / "statements.json").read_text())
    out_dir = run_dir / "claims"
    out_dir.mkdir(exist_ok=True)
    results_path = run_dir / "results.json"
    results = json.loads(results_path.read_text()) if results_path.exists() else {}

    todo = [i for i in claim_items(run_dir, only) if i["id"] in statements]
    skipped = [i["id"] for i in claim_items(run_dir, only) if i["id"] not in statements]
    if skipped:
        print(f"skipped {len(skipped)} claim(s) with no statement in statements.json"
              f" (run `state`): {', '.join(skipped)}")
    decisions, backs = load_decisions(run_dir), load_backtranslations(run_dir)
    problems = {i["id"]: approval_problem(decisions, backs, i["id"],
                                          statements[i["id"]]["statement"]) for i in todo}
    if not unreviewed:
        for cid, problem in problems.items():
            if problem:
                print(f"prove {cid}: refused, {problem}")
        todo = [i for i in todo if not problems[i["id"]]]

    def record(item: dict, result: dict) -> None:
        if problems[item["id"]]:
            result["unreviewed"] = True
        results[item["id"]] = result
        results_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")

    # One at a time until a model call has written the shared prompt to the
    # cache; then the rest in parallel, all reading it back. Each claim's
    # output is buffered and printed whole when it finishes.
    calls_before = len(SPENT)
    while todo and len(SPENT) == calls_before:
        item = todo.pop(0)
        record(item, prove_one(item, statements[item["id"]]["statement"],
                               defs_lean, ns, out_dir))
    if todo:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = {pool.submit(buffered, prove_one, item,
                                   statements[item["id"]]["statement"],
                                   defs_lean, ns, out_dir): item for item in todo}
            for f in as_completed(futures):
                output, result = f.result()
                print(output, end="", flush=True)
                record(futures[f], result)

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
        epilog="Steps, in order: extract, defs, state, backtranslate, approve, prove. "
               "Review statements.json (with backtranslations.json), then `approve`: "
               "prove takes only approved statements.")
    parser.add_argument("step", choices=["extract", "defs", "state", "backtranslate",
                                         "approve", "prove"])
    parser.add_argument("paper", type=Path, help="the paper's LaTeX source (one .tex file)")
    parser.add_argument("claim", nargs="*",
                        help="state/backtranslate/approve/prove: only these claim ids "
                             "(default: all claims)")
    parser.add_argument("--override", action="store_true",
                        help="approve: even if back-translation is missing, stale or "
                             "flagged (recorded in decisions.json)")
    parser.add_argument("--unreviewed", action="store_true",
                        help="prove: also statements not approved (for testing); "
                             "their results are marked unreviewed")
    parser.add_argument("--jobs", type=int, default=PROVE_JOBS, metavar="N",
                        help=f"prove: claims proved at once (default {PROVE_JOBS})")
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
    elif args.step == "backtranslate":
        backtranslate(args.paper, run_dir, args.claim)
    elif args.step == "approve":
        approve(run_dir, args.claim, args.override)
    elif args.step == "prove":
        prove(run_dir, args.claim, args.jobs, args.unreviewed)
    print(f"\n{len(SPENT)} model call(s), ${sum(SPENT):.2f}")


if __name__ == "__main__":
    main()
