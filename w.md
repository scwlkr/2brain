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
Initial delivery merged as PR17 at 217f6ab and published as 0.1.3-dev.217f6ab.
Merging main invokes the existing npm dev publisher; further releases need approval.

## Wiki model setup refinement (2026-10-20)

Branch: codex/wiki-setup-validation, based on verified main/PR17. Added offline
`wiki agent --check` with JSON support before context initialization, shared model
configuration validation, actionable/redacted provider diagnostics and retry
guidance. No importer redesign: existing inbox capture/retry behavior was verified
using synthetic Markdown/JSON exports, including repeat runs and changed evidence.
Real CLI/model-adapter subprocesses use a simulated provider for the end-to-end
test; no live model, account exporter, audio service or scheduler was activated.
Published npm dev version and CLI version/help were checked independently.
See docs/llm-wiki.md for setup checks and local troubleshooting. Review the scoped
draft before any merge: current authorization does not cover another npm release.
