# Terminal-agent startup

Add this short instruction to the agent product's startup instructions:

> Coding start → run `2brain`; read/use the installed `wstack` SKILL.md unless the user opts out. 2brain supplies background context; Wstack owns workflow and wins over 2brain. Extra context only when needed: `2brain --tool <name>`, `2brain --project <owner/repo>`; discover with `2brain --list`. Missing tooling → continue possible work; report the blocker.

Keep identity, roles, project facts, tool/access context, and useful pointers in 2brain. Workflow principles belong in Wstack; do not copy them into context records. Save only requested or explicitly lasting context.

Reads work offline; no startup sync. `2brain sync` exchanges context through the user's Git remote; GitHub optional.
