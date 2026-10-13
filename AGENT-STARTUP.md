# Terminal-agent startup

Add this short instruction to the agent product's startup instructions:

> Near the start of a coding session, run `2brain`. Treat its personalization as defaults; current user instructions take precedence. Use `2brain --tool <name>` for relevant tools and `2brain --project <owner/repo>` for the actual repository; project guidance overrides general defaults. Use `2brain --list` to discover names. Save context only when the user requests it or explicitly states a lasting preference; never infer it from routine activity, suggestions, experiments, or assistant examples. If unavailable, continue the task and report the setup issue briefly.

No automatic synchronization is required at startup. Reads work offline. Sync explicitly with `2brain sync` when exchanging changes through a Git remote the user owns. GitHub is optional; any ordinary Git remote works.
