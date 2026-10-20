<!-- wstack:begin setup -->
Wstack: 0.2.0
Features: [FEATURES.md](FEATURES.md)
Terms: [GLOSSARY.md](GLOSSARY.md)
CLI: `./project --help`
<!-- wstack:end setup -->

## LLM wiki delivery (2026-10-20)

Added optional Karpathy-style Markdown memory under the existing context Git repo.
Commands: wiki init/ingest/compile/query/lint/digest/cycle/agent. Includes a JSON
model adapter, agent contract, immutable capture/provenance checks on save/sync,
revision-checked compilation, generated index/log, cited narrative output and
optional external TTS. Existing JSON personalization and offline reads preserved.
See docs/llm-wiki.md and skills/wiki-lint/SKILL.md. Recurring execution is documented
for a persistent scheduler; no private account connectors or scheduler activated.
Model-provider calls require user environment credentials; live provider/audio
services were not available in the cloud fixture. Tests use deterministic adapters.
Delivery is on feat/llm-wiki; merging main invokes the existing npm dev publisher.

## Local wiki model integration (2026-10-20)

`wiki local [--setup]` checks Ollama and real JSON inference without a context
repository. Setup reuses `qwen3.5:35b` and creates a `2brain-wiki` alias at 32K.
Compile/query/digest/cycle accept `--local`; `wiki agent --local` exposes the same
adapter. Local requests ignore hosted credentials/settings, allow only loopback
HTTP(S), bypass proxies and reject redirects/cloud model names with no fallback.
Remote endpoints retain HTTPS and credential validation. The daemon itself must
have cloud features disabled; CLI subprocess environment alone cannot change an
already-running server. See docs/llm-wiki.md for persistent configuration.

Real local preflight exposed conflicting compilation/narrative contracts; queries
and reports now receive only their own output schema, with explicit inline links.
Native Mac terminal checks required PTY draining through exit and reading restored
attributes from the master after Darwin revokes the slave. Production TUI code is
unchanged. Personal context, private sources, existing models and scheduling are
outside these tests; runtime verification uses isolated synthetic contexts.
