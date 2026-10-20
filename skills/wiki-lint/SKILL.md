---
name: wiki-lint
description: Audit a 2brain LLM wiki for broken evidence, stale index, gaps, and contradictory claims.
---

1. Run `2brain wiki lint --json`. Check errors before trusting the wiki.
2. Read `2brain wiki query` (index first), then recently changed topics via
   `2brain wiki query --page log.md` and their linked source evidence.
3. Resolve missing links and stale synthesis through `2brain wiki compile`.
   Incorporate pending sources; preserve claims that still have evidence.
4. Flag contradictions explicitly with citations and confidence. Do not silently
   choose a winner or invent support. Consolidate overlapping topics by adding
   links and explaining their relationship; do not delete source evidence.
5. Never modify raw files or provenance to make a check pass. If an immutable
   source changed, report the problem and restore the original from known Git
   history before continuing.
6. Rerun lint. Report the revision, fixed issues and remaining source/knowledge
   gaps. A structurally clean wiki does not establish that every claim is true.

This skill authorizes local audit and corrections requested by the user. It does
not authorize new account connections, public sharing or sending messages.
