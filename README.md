# semantics-formalizer
A procedure for auto-formalizing a semantics paper in Lean.

See [SPEC.md](SPEC.md) for what the project does and [TODO.org](TODO.org) for progress.

> **Tested only with Claude.** The design is agent- and model-agnostic (see
> SPEC.md §4, "Agent and model independence"), but the pipeline has only
> been run with Claude: model calls go through `claude -p`, and the project
> is developed in Claude Code. Other agents or models may work, but are
> unsupported until they pass the acceptance suite.
