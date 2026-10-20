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
The trusted CLI contract is included in the system message; captured evidence
stays in the user payload. Local sampling uses temperature zero. Duplicate
model-generated index/log output is discarded because the CLI regenerates those
files from validated topics; topic/source/link/revision validation remains intact.
Local questions with no lexical matches receive up to five topics in index order
so broad questions have source content; this is a bounded overview, not exhaustive
retrieval. MLX alias setup caches full base/alias digests outside context data
because newer Ollama Modelfiles use self names rather than shared blob paths.
Installed-package verification exposed occasional missing inline narrative
citations. Local narratives get one correction attempt with the same model and
evidence, followed by the unchanged strict validator; external agents keep their
existing one-attempt behavior. Endpoint/JSON transport failures are not retried.
Narrative contracts enumerate the actual allowed topic paths. This avoids local
models treating raw-source links or bare topic filenames as citation-array values.
Local narrative JSON schemas restrict citation values to that same path list;
hosted requests and compilation/health JSON-object requests are unchanged.
The local adapter canonicalizes redundant wiki/ and ../wiki/ prefixes on flat
topic links, then the existing validator still rejects unknown or unsafe targets.
The local adapter renders missing links for already-declared, supplied citations
in a Cited pages section, avoiding unreliable model formatting. It does not add
source IDs or accept paths outside the provided evidence; final validation stays.
Native Mac terminal checks required PTY draining through exit and reading restored
attributes from the master after Darwin revokes the slave. Production TUI code is
unchanged. Personal context, private sources, existing models and scheduling are
outside these tests; runtime verification uses isolated synthetic contexts.
