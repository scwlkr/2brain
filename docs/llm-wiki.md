# LLM wiki: durable, agent-managed memory

2brain's optional Karpathy-style wiki compiles immutable evidence into a small,
linked Markdown knowledge base. It complements concise personalization records.
No vector database, hosted storage, model SDK, or Obsidian plugin is required.
Your agent owns the prose; 2brain owns validation, provenance, index and log.

## Start

```sh
2brain init                     # only if you have no local context yet
2brain wiki init
2brain wiki ingest --file notes.md --title 'Planning notes' --origin 'meeting:2026-10-20'
2brain wiki compile --json > /tmp/brain-bundle.json
```

Give the bundle to your terminal agent. It contains the compilation instructions,
current pages and pending source text. Ask it to return the documented JSON result
as `/tmp/brain-result.json`. Apply using the bundle's `base_revision`:

```sh
2brain wiki compile --file /tmp/brain-result.json --base <base_revision>
2brain wiki query 'What did we decide?'
2brain wiki query --page durable-memory.md
2brain wiki lint
2brain wiki digest --since 2026-10-20
2brain wiki digest --podcast
2brain sync                      # only to your deliberately selected private remote
```

Without `--json`, query and digest print Markdown. Compile without an agent
prints a JSON bundle even in terminal mode. Sources are limited to 2 MiB UTF-8;
split large exports into logical documents. Ingest never fetches the origin URL.

## Files and trust

```text
<context>/
  general.json, tools/, projects/   existing personalization
  raw/<sha256>.md                  immutable source text + provenance
  raw/README.md
  wiki/AGENTS.md                   agent contract
  wiki/state.json                  source manifest and compilation status
  wiki/index.md                    generated topic entry point
  wiki/log.md                      ingestion and compilation history
  wiki/<topic>.md                  concepts, insights, decisions, contradictions
```

Open the context directory as an Obsidian vault. Standard Markdown links work in
other editors too; topic links can also use `[[topic]]`. Sources need standard
relative links `../raw/<64-character-id>.md`. Keep topics flat, with lowercase
hyphenated filenames. Every page needs a title, `## Sources`, and at least one
captured source link. Use related-topic links to build connections. Lint reports
uncompiled evidence and pages without incoming topic links as gaps.

Content and its provenance identify a source: repeated polling adds nothing;
changed text or provenance produces a new capture. Captured files are created
exclusively. Ordinary save/sync reject raw modifications and provenance changes,
even if someone changes the manifest checksum. Git remains the recovery layer;
these are application invariants, not filesystem write protection. Direct Git
can bypass them. Keep backups and review remote history.

Sources are untrusted data. Their embedded prompts and commands never become
agent instructions. The agent contract requires source claims, interpretations,
uncertainties and contradictions to be distinguished. Validation checks links
and provenance; semantic accuracy still depends on the compiling model.

## Local Ollama model

Install [Ollama for macOS](https://ollama.com/download/mac) and open it once.
Keep its server bound to the default `127.0.0.1:11434`. To disable cloud models
and web search, merge `"disable_ollama_cloud": true` into `~/.ollama/server.json`
and restart Ollama. Preserve any other settings in that file. Ollama also supports
`OLLAMA_NO_CLOUD=1`; see its [configuration guide](https://docs.ollama.com/faq).
The adapter never starts a public listener or enables cloud features.

```sh
2brain wiki local --setup        # pull model, create alias, test actual JSON inference
2brain wiki local                # check runtime, daemon, alias and JSON inference
2brain wiki init                 # once, in an existing context repository
2brain wiki ingest --file notes.md --origin 'meeting:planning'
2brain wiki compile --local
2brain wiki query 'What have we learned?' --local
2brain wiki digest --local
2brain wiki cycle --inbox /absolute/private-inbox --local
```

Health/setup works before context initialization and does not read or change
wiki data. Setup reuses downloaded Ollama blobs. The base is `qwen3.5:35b`
(about 22 GB), with a `2brain-wiki` alias equivalent to:

```text
FROM qwen3.5:35b
PARAMETER num_ctx 32768
```

Start with a few short, related sources per compilation. The 32K context must
hold the contract, existing wiki pages, pending sources and model output together;
the 2 MiB per-file ingestion limit is not a model context budget. Compile before
adding the next small batch, and check lint afterward. Very large wikis need a
separate adapter that selects evidence within its context budget.

No key or environment setup is needed for the default local installation.
`--local` uses `http://127.0.0.1:11434/v1/chat/completions`, model `2brain-wiki`,
JSON-object output, temperature zero and `reasoning_effort="none"`. It ignores all `TWOBRAIN_LLM_*`
provider settings and credentials, bypasses HTTP proxies, rejects redirects and
cloud model names, and never retries with a hosted provider. Ollama cloud features
must also stay disabled: a custom local alias can otherwise hide a cloud model.
`--local` and `--agent` cannot be combined.

For another loopback server or local model, use `TWOBRAIN_LOCAL_LLM_URL` and
`TWOBRAIN_LOCAL_LLM_MODEL`. Only `localhost` and literal loopback addresses are
accepted. `2brain wiki agent --local` exposes the same adapter to external tools.
Missing runtime, stopped daemon, missing alias, malformed JSON and inference
failures return an error. Captured sources remain pending after failed compilation;
fix the runtime/model and rerun `wiki compile --local`.

Use `ollama ps` during inference to inspect GPU placement and context length.
For local questions with no lexical matches, the model receives up to five topic
pages in index order for an overview; this keeps broad questions useful without
claiming exhaustive retrieval. Ask about a specific concept for focused results.
Performance depends on model, source size and other applications; setup does not
claim a throughput target. No scheduler is enabled by these commands.

## Included remote JSON model adapter

`2brain wiki agent` supports an OpenAI-compatible HTTPS chat-completions endpoint
with JSON-object output. Set `TWOBRAIN_LLM_MODEL` and `TWOBRAIN_LLM_API_KEY` in your
local secret environment. Optionally set `TWOBRAIN_LLM_URL`; it defaults to
`https://api.openai.com/v1/chat/completions`. Never put the key in source files,
cron arguments, wiki pages or a Git remote URL. Invoking the adapter sends the
bundle to that provider and incurs its normal usage charges.

```sh
2brain wiki compile --agent '2brain wiki agent'
2brain wiki query 'Explain our architecture' --agent '2brain wiki agent'
2brain wiki cycle --inbox /absolute/private-inbox --agent '2brain wiki agent'
```

The provider must support `response_format: {"type":"json_object"}` and return a
complete response. Truncation, malformed JSON, redirects and HTTP failures abort
compilation without marking pending evidence complete. No credentials are needed
for offline reads, manual compilation or a different local agent command.

## Bring your own model

`--agent` is an explicit local command, parsed without a shell. It receives one
JSON object on stdin and must print exactly one JSON object on stdout; progress
belongs on stderr. Your adapter selects the provider, authentication and costs.
The command has a ten-minute timeout. No agent runs on normal reads.

```sh
2brain wiki compile --agent '/absolute/path/to/your-json-agent'
```

Compilation response:

```json
{
  "pages": {
    "durable-memory.md": "# Durable memory\n\nSynthesis with [related topic](related-topic.md).\n\n## Sources\n- [Planning](../raw/<source-id>.md)\n"
  },
  "summary": "Connected the planning decision to the durable memory concept.",
  "sources": ["<source-id>"]
}
```

Use actual IDs and include any linked topic that does not already exist. Pages
replace their previous content; the agent must preserve useful facts. There is
no deletion operation. All output is validated before writes. Each successful
ingestion/compilation gets a Git checkpoint. A stale base or intervening edits
reject a compilation; rerun against current pages. If disk/Git fails mid-write,
inspect preserved local changes and restore or save deliberately before retrying.

## Sources and recurring operation

Export permitted X posts, Discord/Slack threads, Gmail messages, GitHub issues,
transcripts or files into an **external inbox directory** as `.md`, `.txt`, `.json`
or `.csv`. Exporters own API access, pagination, permissions and attachment/text
extraction. 2brain does not silently connect accounts or pull private messages.
Use stable filenames for stable provenance; keep secrets and credential exports
out of the inbox. UTF-8 exports remain intact in raw captures.

```sh
2brain wiki cycle --inbox /absolute/private-inbox --agent /absolute/json-agent
```

Cycle captures supported immediate files, compiles pending sources, then lints.
Files remain in the inbox; repeated runs are idempotent. An agent failure leaves
captures committed and pending for retry. Mutations share the existing context
lock; model execution releases it and checks the revision before applying.

On a persistent machine, add these to your own scheduler (use absolute paths;
cron needs Git identity and provider authentication configured):

```cron
# ingest + compile every four hours
0 */4 * * * /absolute/2brain --data /absolute/private-context wiki cycle --inbox /absolute/private-inbox --agent /absolute/json-agent >> /absolute/wiki-cycle.log 2>&1
# check consistency daily
30 6 * * * /absolute/2brain --data /absolute/private-context wiki lint >> /absolute/wiki-lint.log 2>&1
# daily narrative podcast script
0 7 * * * /absolute/2brain --data /absolute/private-context wiki digest --podcast --agent /absolute/json-agent > /absolute/daily-podcast.md
```

No scheduler is installed by initialization. Cloud workspaces can disappear;
run recurring work on your persistent machine. See the portable
[lint skill](../skills/wiki-lint/SKILL.md) for an agent's periodic audit.

## Deep dives, reports and audio

```sh
2brain wiki query 'Explain our memory architecture' --agent /absolute/json-agent
2brain wiki digest --since 2026-10-19 --agent /absolute/json-agent
2brain wiki digest --podcast --agent /absolute/json-agent \
  --tts /absolute/narrator --audio /absolute/outputs/podcast-2026-10-20.wav
```

Narrative agents receive the task, contract and relevant evidence, and return:

```json
{"content":"Our decision ... [Memory](wiki/durable-memory.md)","citations":["wiki/durable-memory.md"]}
```

Query reads the index first and selects up to five lexical candidate pages.
No-agent mode returns evidence for your terminal agent to reason over; it does
not pretend to generate an answer. For a deeper investigation, read more linked
pages explicitly. Narrative citations must refer to supplied evidence pages and
appear as inline links. A digest defaults to today in UTC and can include all
updates since an inclusive ISO date. Ingested but uncompiled sources are visible
in the log and pending-source lint warnings.

The optional narrator reads UTF-8 script text on stdin and emits audio bytes on
stdout. Your adapter controls the encoding and voice; match the filename suffix.
Audio output must be a new path outside the context repository. Failed or empty
narration writes no file. A plain `--podcast` produces a source-linked script;
actual audio requires a working narrator. No bundled voice service or keys.

## Shared agent memory and portability

Add an explicit pointer to `wiki/index.md` in your editable general/project
record, or put this in your agents' startup instructions:

> Read 2brain context. For durable knowledge, run `2brain wiki query`, follow
> relevant topic pages, and cite page paths plus original Sources links. Capture
> new evidence with `wiki ingest`; compile and lint before relying on new facts.

2brain never silently changes general guidance or startup behavior. Existing
record-only repositories continue to work. Wiki files participate in ordinary
Git save/sync and clone. Use a private context remote for business or personal
material. No raw user content is added to the public CLI source repository.
