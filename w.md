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
