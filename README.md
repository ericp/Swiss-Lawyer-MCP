# Swiss Lawyer MCP

Swiss Lawyer is a local MCP and RAG application that provides informational guidance about Swiss immigration and administrative procedures using official Swiss sources. It asks for relevant missing details, retrieves evidence from a local knowledge base, generates a grounded answer, and can save procedure progress for later continuation.

> Swiss Lawyer provides informational guidance only. It is not a lawyer and does not provide legal advice.

## Current coverage

The application is designed to support all Swiss cantons, but the current knowledge base is focused on federal procedures and Zurich.

- Federal Swiss sources: partial coverage
- Canton of Zurich: partial canton-specific coverage
- Other cantons: architecture supported, but canton-specific source coverage is not yet complete

> For a question about an unsupported canton, Swiss Lawyer may provide supported federal information, but it must clearly state when canton-specific evidence is unavailable. It must never use Zurich-specific authorities as a substitute for another canton.

## How it works

```text
Official sources configured in sources.yaml
↓
Enabled remote sources are downloaded; local seed sources are indexed
↓
User asks a question through ChatGPT
↓
Swiss Lawyer detects the procedure and relevant canton
↓
It searches the local official-source knowledge base
↓
It returns a grounded answer, sources, and procedure steps
```

`data/pdfs/metadata/sources.yaml` is the project's approved source list. It tells the synchronizer which official government PDFs and webpages may be downloaded and indexed.

During first-time setup, enabled official remote sources are downloaded to the developer's machine and indexed in ChromaDB. They are not downloaded again for every question. The current demo seed PDFs are local-only entries, so bootstrap indexes them from the repository's local seed files instead of downloading them from remote URLs.

## Prerequisites

Before starting, install:

- Git
- Docker Desktop or Docker Engine with Docker Compose
- Ollama
- Python 3, used by the setup scripts and local development tools
- ngrok, only when connecting the local MCP to ChatGPT through a public HTTPS URL

Plan for roughly 5-10 GB of free disk space. Most of that is Docker images and Ollama models, not the official documents.

## First-time setup

```bash
git clone <repository-url>
cd <repository-directory>
./scripts/bootstrap_local.sh
```

The bootstrap script checks Docker and Ollama, downloads missing Ollama models, creates the local environment configuration, downloads enabled official remote sources from `sources.yaml`, builds the local ChromaDB index, starts the API and MCP services, and runs health checks.

No OpenAI API key is required in local mode. Developers do not need to download PDFs manually. Only enabled and valid remote sources configured in `sources.yaml` are downloaded. The script does not automatically download information for every Swiss canton unless those sources are present in `sources.yaml`.

## Connect to ChatGPT

1. Start ngrok:

```bash
./scripts/run_ngrok.sh
```

2. Copy the HTTPS forwarding URL displayed by ngrok.

3. Add `/mcp` to the end:

```text
https://example.ngrok-free.app/mcp
```

4. In ChatGPT, create or configure the custom MCP connection using:

- URL: the ngrok HTTPS URL ending in `/mcp`
- Authentication: No authentication

5. Confirm that ChatGPT discovers these four tools:

- `consult_swiss_procedure`
- `get_my_procedures`
- `update_my_procedure`
- `delete_my_swiss_lawyer_data`

Keep Docker, Ollama, and ngrok running while using the MCP through ChatGPT.

> The ngrok endpoint is publicly reachable while the tunnel is running. This setup uses a single local identity and no user authentication, so it is suitable only for private testing and portfolio demonstrations.

Do not expose FastAPI port `8000` or Ollama port `11434`.

## Use the MCP

### Ask about a Zurich employment procedure

```text
I am an Australian citizen and I have received a job offer in Zurich. What do I need to do to work there legally?
```

### Continue a procedure

```text
Show my saved procedures and continue the active one.
```

### Update progress

```text
I have now registered with the municipality. Update my procedure.
```

The application may ask clarification questions before answering when nationality, canton, employment status, permit status, dates, or other legally relevant details are missing.

Canton-specific questions outside Zurich may have incomplete coverage. The application should say so instead of using Zurich-specific information.

## Start it again later

```bash
./scripts/start_local.sh
```

This starts the existing local services without redownloading documents or rebuilding the knowledge base.

To rebuild Docker images and start:

```bash
./scripts/start_local.sh --build
```

Do not run bootstrap every time.

## Stop

```bash
./scripts/stop_local.sh
```

This stops the Docker services but preserves downloaded sources, ChromaDB, SQLite memory, and Ollama models.

## Important limitations

- Current official-source coverage is partial.
- Zurich is currently the only canton with confirmed canton-specific source coverage.
- Other cantons need their own verified official sources added to `sources.yaml` before canton-specific answers can be complete.
- Bootstrap downloads all enabled remote sources currently configured in `sources.yaml`. Local-only or disabled entries are not downloaded.
- Documents are synchronized and indexed locally; they are not downloaded again for every question.
- Local mode uses Ollama and does not call OpenAI.
- The MCP server uses no user authentication and one fixed local identity.
- This setup is for private local testing and portfolio demonstration, not public multi-user production.


## Refresh official sources

```bash
docker compose exec api python -m backend.synchronizer.cli sync --all
```

This checks the enabled official sources in `sources.yaml` and updates local copies when they have changed.

For a full reindex:

```bash
docker compose exec api python -m backend.ingestion.index --reset
```

A full reindex is normally unnecessary unless sources or embedding configuration changed.

## Simple troubleshooting

### Docker is not running

Open Docker Desktop and wait until the Docker engine is ready.

### Ollama is not running

Open Ollama or start its local service, then check:

```bash
ollama list
```

### ChatGPT cannot connect

Confirm:

- Docker services are running
- ngrok is running
- the configured URL ends in `/mcp`
- the MCP health check passes

Run:

```bash
./scripts/check_local_mcp.sh
```

### The answer references the wrong canton

This is a bug. The application must use federal sources plus the requested canton and never another canton as a fallback.

## Technical documentation

The sections below describe the internals for developers who want to modify or extend the project.

## Local configuration

Default local mode:

```env
AI_MODE=local

EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text

GENERATION_PROVIDER=ollama
GENERATION_MODEL=llama3.2

PLANNER_PROVIDER=ollama
PLANNER_MODEL=llama3.2

RERANKER_PROVIDER=disabled

OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_TIMEOUT_SECONDS=180

MCP_AUTH_MODE=single_user
MCP_SINGLE_USER_KEY=<generated-local-secret>
INTERNAL_SERVICE_TOKEN=<different-generated-local-secret>
```

Inside Docker, the API uses:

```text
http://host.docker.internal:11434
```

Optional OpenAI provider settings remain in `.env.example` for future experimentation only. They are unused in `AI_MODE=local`, require separate OpenAI billing if enabled intentionally, and are not required for normal local setup.

## Source registry status

Real status of `data/pdfs/metadata/sources.yaml` right now:

- total registry entries: `9`
- enabled remote sources: `0`
- enabled remote PDF sources: `0`
- enabled webpage sources: `0`
- enabled landing-page sources: `0`
- regions with confirmed source coverage: `federal`, `zh`
- canton-specific coverage currently confirmed: Zurich only
- local-only entries: `9`

Local-only entries:

- `seed_federal_b_permit_gainful_activity`
- `seed_federal_b_permit_sem`
- `seed_federal_citizenship_overview`
- `seed_federal_family_reunification`
- `seed_federal_free_movement_eu_efta`
- `seed_federal_residence_permits_overview`
- `seed_federal_without_gainful_activity`
- `seed_zh_driving_licence_exchange`
- `seed_zh_registration_zurich`

Bootstrap can download enabled remote sources when they exist. With the current registry, the remote-download count is zero; bootstrap validates the registry, records local-only seed sources, and indexes the existing local seed PDFs.

## Nationality routing

Swiss Lawyer normalizes stated nationalities with the ISO 3166 country dataset provided by `pycountry`, then routes the user into one Swiss immigration category:

- `swiss`
- `eu_efta`
- `uk`
- `third_country`
- `special_or_unknown`

Country names, alpha-2 codes, alpha-3 codes, common aliases, and common English demonyms are normalized deterministically. Citizenship and residence are treated separately, so "American citizen living in Spain" remains a US/third-country case with Spain only as the residence country.

Explicit current-turn citizenship facts override conflicting saved SQLite memory for the active request. Confirmed nationality updates also store derived fields such as country code and nationality category so memory does not drift into contradictory values.

Dual nationality, ambiguous wording, stateless/refugee/asylum/protected-person status, and unknown nationality inputs are treated as `special_or_unknown` and may require clarification. The system must not silently choose the more favorable citizenship or guess a legal category.

Retrieval is filtered by both canton and nationality category. For example, a Zurich third-country case may use federal sources plus Zurich sources only when they are applicable to `all` or `third_country`; EU/EFTA-only evidence is excluded. If matching official evidence is unavailable, Swiss Lawyer returns insufficient context instead of using a similar but legally inapplicable category.

Correct classification does not guarantee complete legal coverage. Answers remain limited to the official sources currently indexed.

## Storage Roles

Swiss Lawyer MCP uses two separate storage systems:

- **ChromaDB** stores official Swiss knowledge and document chunks.
- **SQLite** stores user-specific memory: profile facts, saved procedures, progress, and concise summaries.

Keeping these stores separate prevents user memory from mixing with the legal/procedural knowledge base.

## Run Ingestion

```bash
python -m backend.ingestion.index --reset
```

The command scans `data/pdfs/`, extracts text page by page with PyMuPDF, chunks extracted text, generates Ollama embeddings with `nomic-embed-text`, and writes the chunks into the model-specific ChromaDB collection, for example `swiss_lawyer__ollama__nomic_embed_text`.

The `--reset` flag deletes and recreates only the currently selected ChromaDB collection. It does not delete PDFs, SQLite memory, synchronization metadata, or unrelated ChromaDB collections.

## Hybrid Retrieval

Phase 2 retrieves candidate chunks from the existing ChromaDB collection using two methods:

- **Vector search** embeds the user question with the configured embedding provider. In default local mode this is Ollama `nomic-embed-text`.
- **BM25 keyword search** loads all stored ChromaDB chunks, tokenizes their text, builds a `rank-bm25` index, and scores chunks against the user's query terms.

The `HybridRetriever` runs both methods, merges the results, removes duplicate chunk IDs, and preserves retrieval source information. It does not rerank and does not generate answers.

## Reranking

Hybrid retrieval is good at recall: vector search can find semantically similar chunks, while BM25 can catch exact keyword matches. It can still return candidates that are only loosely related to the question. Reranking improves precision by scoring each merged candidate directly against the question.

Phase 3 can use a local Sentence Transformers CrossEncoder:

```text
cross-encoder/ms-marco-MiniLM-L-6-v2
```

For each candidate, the reranker scores the pair:

```text
(question, chunk text)
```

The default local developer setup uses `RERANKER_PROVIDER=disabled` so Docker stays lightweight and does not install PyTorch, CUDA/NVIDIA packages, or `sentence-transformers`. In disabled mode, the system preserves the reranking result schema and uses hybrid retrieval ordering/scores. CrossEncoder reranking remains available only if the optional provider and dependencies are intentionally installed later.

The current architecture is:

```text
Question
↓
Hybrid Retrieval
↓
Merged Candidates
↓
Reranker
↓
Top Relevant Chunks
```

## Clarification

Clarification is schema-driven. Before retrieval and answer generation, the system classifies the user's intent and checks the known user profile against deterministic procedure schemas.

Current clarification architecture:

```text
Question
↓
Intent Classification
↓
Clarification Engine
↓
Clarification Questions
↓
(Next phase: Answer Generation)
```

Each supported procedure has one centralized schema in `backend/clarification/procedure_schemas.py`. A schema defines:

- intent name
- required fields
- optional fields
- field descriptions
- default clarification question for each required field
- intent keywords

The clarification engine asks all and only missing required fields for the detected procedure. This matters in legal and administrative workflows because nationality, canton, permit status, purpose of stay, and dates can materially change eligibility, documents, competent authority, steps, timelines, and applicable federal or cantonal rules.

Asking fewer but more relevant questions improves the user experience and avoids unnecessary LLM calls. It is also safer and easier to test: required information is determined by versioned schemas, not by a model improvising case-by-case.

To add a new procedure, add one entry to `PROCEDURE_SCHEMAS` with its required fields, optional fields, descriptions, questions, and keywords. The classifier and clarification engine will use it automatically.

## Test Clarification

```bash
python -m backend.clarification.test_clarification \
  "Can I move to Switzerland as a Brazilian citizen?" \
  --profile-json '{"nationality":"Brazil"}'
```

## Grounded Answer Generation

Phase 5 adds final answer generation after clarification, hybrid retrieval, and reranking. The generator receives the user question, detected intent, completed user profile, and top reranked chunks. It does not perform retrieval.

Current end-to-end architecture:

```text
Question
↓
Clarification
↓
Hybrid Retrieval
↓
Reranker
↓
Grounded Answer Generation
```

Grounded generation uses a reusable system prompt stored in `backend/prompts/grounded_answer_system_prompt.txt`. In default local mode, `llama3.2` runs through Ollama `/api/chat`. The prompt instructs the model to answer only from supplied official context, never invent rules, documents, deadlines, authorities, or procedures, and explicitly say when retrieved context is insufficient.

The generated answer is structured as:

- short direct answer
- explanation
- procedure steps
- important notes
- cited official sources
- deterministic confidence label
- insufficient-context flag

If no reranked context is available, the generator does not call a model. It returns:

```text
The retrieved official documentation does not contain enough information to answer this question completely.
```

### Source Attribution

Every generated answer includes source attribution from the reranked chunks. Citations include source filename, page number when available, and region. This is essential for legal/procedural workflows because users need to see where guidance came from, and later evaluation can verify whether the answer was actually grounded in official evidence.

### Confidence Estimation

Confidence is not GPT self-reported confidence. It is estimated deterministically from retrieval quality signals:

- number of reranked chunks
- number of unique sources
- average rerank score

This keeps confidence tied to evidence quality rather than model tone.

## Test Generation

```bash
python -m backend.generation.test_generation \
  "Can a Brazilian citizen work in Switzerland?" \
  --profile-json '{"nationality":"Brazil","employment_status":"Swiss job offer","purpose_of_stay":"work","intended_canton":"Zurich"}'
```

## Planner & Workflow Engine

Phase 6 converts a grounded answer into an actionable procedure workflow. The planner receives the user question, detected intent, completed profile, generated answer, citations, and reranked evidence. It does not perform retrieval and does not invent missing procedural details.

Current architecture:

```text
Question
↓
Clarification
↓
Hybrid Retrieval
↓
Reranker
↓
Grounded Answer Generation
↓
Planner & Workflow Engine
```

Answer generation explains what the retrieved evidence supports. Planning turns that grounded explanation into a workflow with:

- title and summary
- step-by-step plan
- required documents
- estimated timelines
- potential blockers
- next recommended action
- workflow status
- source references
- missing information

The planner prompt is stored in `backend/prompts/workflow_planner_system_prompt.txt`. It instructs the model to use only the grounded answer and cited evidence. Unsupported deadlines, documents, offices, fees, authorities, or eligibility rules must be written as:

```text
Not specified in retrieved sources.
```

Workflow status values are:

- `ready_to_start`: enough information exists to begin.
- `needs_more_information`: important information is missing.
- `blocked`: the grounded answer indicates the user may not currently qualify or cannot proceed.
- `in_progress`: reserved for future memory support.
- `completed`: reserved for future memory support.

These statuses prepare the project for SQLite memory in Phase 7 because a future persistent workflow record can track whether a user has started, completed, or is blocked on specific procedure steps.

## Test Planner

```bash
python -m backend.planners.test_planner
```

## SQLite Memory

Phase 7 adds persistent, structured user memory at:

```text
data/sqlite/memory.db
```

The memory layer stores only procedure-relevant structured information. It does not store API keys, passwords, identity documents, uploaded document contents, or full conversation transcripts by default. It stores concise summaries and JSON-compatible profile facts that can be inspected and deleted.

### Database Schema

The initial Alembic migration creates:

- `users`: user records with optional `external_user_key`
- `user_profile_facts`: flexible confirmed or unconfirmed profile facts keyed by `user_id + field_name`
- `procedures`: saved `ProcedurePlan` JSON, workflow status, current step, and progress timestamps
- `procedure_interactions`: concise interaction summaries and optional structured payloads

Profile facts are flexible so new clarification fields can be added without a database migration.

### Migrations

Run migrations before using the real memory database:

```bash
.venv/bin/alembic upgrade head
```

Tests run migrations against temporary SQLite databases and do not modify `data/sqlite/memory.db`.

### Memory CLI Demo

```bash
python -m backend.memory.test_memory
```

The demo creates or retrieves a demo user, saves confirmed profile facts, reconstructs a Phase 4 `UserProfile`, saves a Phase 6 `ProcedurePlan`, records an interaction summary, updates procedure status, builds a `MemoryContext`, and deletes a separate demo user.

### Procedure Resumption

`MemoryService.build_memory_context(...)` loads:

- known user profile facts as a Phase 4 `UserProfile`
- an active procedure when a `procedure_id` is supplied
- active procedures filtered deterministically by intent/question and status
- recent interaction summaries
- saved `ProcedurePlan`, latest status, and current step

Future FastAPI and MCP layers can load this context before clarification, so users are not repeatedly asked for already confirmed information.

Updated architecture:

```text
Official PDFs
↓
Ingestion
↓
ChromaDB

User interaction
↓
Clarification
↓
Retrieval and reranking
↓
Grounded answer
↓
Planner
↓
SQLite memory
↓
Future procedure continuation
```

## FastAPI Orchestration

Phase 8 exposes the workflow through FastAPI and connects the existing domain services without duplicating their logic.

Run locally:

```bash
uvicorn backend.api.app:app --reload
```

The API layer is intentionally thin:

- `backend/api/app.py` creates the FastAPI application.
- `backend/api/dependencies.py` wires reusable services and cached expensive components.
- `backend/api/routes/health.py` exposes dependency health checks.
- `backend/api/routes/procedures.py` exposes procedure query, read, update, list, and memory deletion endpoints.
- `backend/orchestration/procedure_orchestrator.py` coordinates clarification, retrieval, reranking, generation, planning, and memory.
- `backend/location/canton_resolver.py` deterministically resolves known Swiss cities to cantons.

Phase 8 architecture before the MCP adapter:

```text
ChatGPT in a later phase
↓
MCP in a later phase
↓
FastAPI
↓
ProcedureOrchestrator
├── SQLite memory
├── Clarification engine
├── Hybrid retrieval
├── Reranker
├── Grounded generation
└── Workflow planner
```

Complete request lifecycle:

```text
Request
↓
Resolve or create user
↓
Load SQLite memory
↓
Persist explicitly confirmed profile updates
↓
Resolve intended city to canton when possible
↓
Intent detection
↓
Clarification engine
↓
If required information is missing: return questions and stop
↓
Hybrid retrieval
↓
Reranker
↓
Grounded answer generation
↓
Planner and workflow engine
↓
Save or update procedure
↓
Record concise interaction summary
↓
Return answer, plan, sources, and procedure state
```

## Local MCP, Docker and ngrok

Phase 11 exposes the Phase 8 workflow to ChatGPT through a local MCP server. The deployment is intentionally private and single-user:

```text
Eric in ChatGPT
↓
ChatGPT Developer Mode app
Authentication: No Authentication
↓
Public ngrok HTTPS endpoint
↓
ngrok agent on Eric's Mac
↓
http://127.0.0.1:8001/mcp
↓
Docker Compose
├── MCP container
│   ├── Four MCP tools
│   ├── Fixed single-user identity
│   └── Internal service authentication
├── FastAPI container
│   └── ProcedureOrchestrator
└── ./data mounted as persistent local storage
```

The MCP server exposes exactly four tools:

- `consult_swiss_procedure`
- `get_my_procedures`
- `update_my_procedure`
- `delete_my_swiss_lawyer_data`

The MCP tool schemas do not accept `user_id`, `external_user_key`, OAuth claims, account IDs, retrieval controls, model names, or prompt configuration. Identity is always injected by `SingleUserIdentityProvider` from:

```bash
MCP_AUTH_MODE=single_user
MCP_SINGLE_USER_KEY=replace-with-a-private-local-key
```

MCP-to-FastAPI calls use a separate internal service token:

```text
Authorization: Bearer <INTERNAL_SERVICE_TOKEN>
```

This authenticates the MCP container to the private FastAPI route group. It is not user authentication.

Use `./scripts/bootstrap_local.sh` for first-time setup, `./scripts/start_local.sh` for normal startup, and `./scripts/run_ngrok.sh` only when you want to expose the local MCP endpoint temporarily to ChatGPT Developer Mode.

Use MCP Inspector locally at:

```text
http://127.0.0.1:8001/mcp
```

Configure ChatGPT Developer Mode with the ngrok URL ending in `/mcp` and choose **No Authentication**. Exact ChatGPT UI wording may change.

Security limitations:

- ngrok forwards public HTTPS traffic to localhost port `8001`.
- FastAPI port `8000` is not publicly exposed by Compose.
- The MCP endpoint has no user authentication.
- One server-side identity owns all stored memory.
- The endpoint is public while ngrok is running.
- The Mac, Docker and ngrok must stay running.
- This setup is suitable only for private testing and portfolio demos.
- OAuth and permanent hosted infrastructure are required before public multi-user use.
- Azure and Azure DevOps are not required.

See [docs/phase-11-mcp.md](docs/phase-11-mcp.md) and [docs/ngrok-chatgpt-setup.md](docs/ngrok-chatgpt-setup.md).

### Endpoints

- `GET /health`: checks application, SQLite, ChromaDB, and the configured local or optional remote AI provider availability.
- `POST /v1/procedures/query`: runs the clarification-first procedure workflow.
- `GET /v1/users/{user_id}/procedures`: lists saved procedures, with optional status, intent, active-only, limit, and offset filters.
- `GET /v1/procedures/{procedure_id}?user_id=...`: reads one saved procedure with recent interaction summaries.
- `PATCH /v1/procedures/{procedure_id}`: updates status, current step, confirmed profile facts, and progress notes.
- `DELETE /v1/users/{user_id}/memory`: deletes user-specific SQLite memory only. It does not delete ChromaDB official knowledge.

### Query Example

```bash
curl -X POST http://localhost:8000/v1/procedures/query \
  -H "Content-Type: application/json" \
  -d '{
    "external_user_key": "demo-user",
    "question": "Can I move to Switzerland as a Brazilian citizen?",
    "profile_updates": {
      "nationality": "Brazil"
    },
    "confirmed_profile_fields": [
      "nationality"
    ]
  }'
```

When clarification is still required, the API stops before retrieval, reranking, generation, and planning:

```json
{
  "state": "clarification_required",
  "needs_clarification": true,
  "missing_fields": [
    "intended_canton",
    "purpose_of_stay",
    "employment_status"
  ],
  "clarification_questions": [
    {
      "field": "intended_canton",
      "question": "Which Swiss canton or city are you planning to move to?"
    }
  ]
}
```

Only profile fields listed in `confirmed_profile_fields` are stored as confirmed memory. Unconfirmed `profile_updates` can be used for the current request, but they are not persisted as confirmed user facts.

### City-to-Canton Resolution

`CantonResolver` maps known Swiss cities deterministically, for example:

- Zurich or Zürich → `ZH`
- Geneva or Genève → `GE`
- Lausanne → `VD`
- Bern or Berne → `BE`
- Basel → `BS`
- Lugano → `TI`

If a city is unknown or ambiguous, the API returns a clarification question instead of guessing a canton.

### Procedure Continuation

When `procedure_id` is supplied, the API verifies that the procedure belongs to the resolved user before reading or updating it. This ownership check exists even though authentication is not implemented yet. Saved procedures keep their validated Phase 6 `ProcedurePlan`, workflow status, current step, and recent concise interaction summaries.

Every query response includes the disclaimer:

```text
This information is based on retrieved official Swiss sources and is provided for informational purposes only. It does not constitute legal advice.
```

## Official Source Synchronizer

Phase 9 keeps the official knowledge base current through a controlled synchronizer. Automatic refresh does not mean unrestricted crawling.

- Approved sources are refreshed automatically.
- New sources are only discovered into a review queue.
- Discovered candidates must be approved before indexing.
- Only official Swiss government domains from the centralized allowlist are accepted.

Current Phase 9 architecture:

```text
Official approved sources
↓
Synchronizer
├── Conditional HTTP checks
├── Change detection
├── PDF and webpage processors
├── Candidate discovery
└── Synchronization audit records
↓
Incremental ingestion
↓
ChromaDB
↓
FastAPI orchestration
↓
Grounded answers
```

### Supported Region Definitions

The synchronizer's region registry includes `federal` plus all 26 Swiss canton codes, so more canton sources can be added later:

```text
ag ai ar be bl bs fr ge gl gr ju lu ne nw ow sg sh so sz tg ti ur vd vs zg zh
```

Region names and approved government domains live centrally in `backend/synchronizer/regions.py`. Domain rules are not scattered across the codebase. This is registry support, not a claim that the current knowledge base already has canton-specific documents for every canton.

### Source Registry

Curated static sources live in:

```text
data/pdfs/metadata/sources.yaml
```

Schema:

```yaml
version: 1
sources:
  - id: sem_family_reunification
    enabled: true
    region: federal
    authority: State Secretariat for Migration
    procedure_types:
      - family_reunification
    source_type: pdf
    url: https://www.sem.admin.ch/...
    language: en
    local_filename: family_reunification.pdf
    discovery_enabled: false
    title: Optional title
    expected_content_type: application/pdf
    css_content_selector: main
    css_link_selector: a
    include_url_patterns: []
    exclude_url_patterns: []
    notes: Optional notes
    priority: 10
    expected_update_frequency: weekly
    replacement_group: family_reunification_federal
    metadata: {}
```

Remote `pdf`, `webpage`, and `landing_page` entries must use HTTPS and pass the region/domain allowlist. Existing manually collected PDFs are preserved as disabled `local_only` seed entries with `local://` URLs and TODO notes instead of fabricated official URLs.

Current registry viability:

- total registry entries: `9`
- enabled remote PDF entries: `0`
- enabled webpage entries: `0`
- enabled landing-page entries: `0`
- local-only seed entries: `9`

That means the current clone contains the demo seed PDFs needed to build the local portfolio knowledge base, while the registry is already structured for future verified official URLs. `./scripts/bootstrap_local.sh` still runs registry validation and synchronization. With the current registry, synchronization records the manually seeded sources and does not download remote documents. When verified HTTPS government URLs are added and enabled, bootstrap will download those sources locally without hard-coding URLs in shell scripts.

### Approved Domain Policy

The synchronizer rejects:

- non-HTTPS remote sources
- redirects that leave the approved allowlist
- blogs, law firms, news sites, social media, private mirrors, shorteners, and arbitrary storage
- path traversal or unsafe local filenames

Final URLs are validated after redirects.

### Database Schema

Phase 9 adds these SQLite tables through Alembic migration `0002_phase_9_synchronizer`:

- `synchronized_sources`: source status, canonical URL, local path, ETag, Last-Modified, SHA-256, document id, failures, timestamps.
- `synchronization_runs`: run status, scope, checked/updated/unchanged/failed counts, discovered candidate count.
- `synchronization_events`: per-source audit events such as `check_started`, `unchanged`, `validated`, `indexed`, `updated`, `failed`, `unavailable`, and candidate review events.
- `source_candidates`: discovered official-looking links awaiting approval, with candidate status `pending`, `approved`, `rejected`, `duplicate`, or `invalid`.

Run migrations:

```bash
.venv/bin/alembic upgrade head
```

### Change Detection

Change detection uses this order:

```text
HTTP 304
↓
ETag comparison
↓
Last-Modified comparison
↓
SHA-256 comparison
```

SHA-256 is the final source of truth. A changed `Last-Modified` header alone is not enough to force reindexing when the content hash is unchanged.

### PDF Synchronization

For approved PDFs:

```text
conditional HTTP request
↓
temporary download
↓
content-type, PDF signature, and PyMuPDF validation
↓
SHA-256
↓
Phase 1 extraction and chunking
↓
embeddings
↓
ChromaDB replace_document(document_id, chunks)
↓
move validated PDF into data/pdfs/<region>/
↓
record sync metadata and events
```

The old local file and old ChromaDB chunks are retained if validation, embedding, or replacement fails.

### Webpage Synchronization

For approved webpages, the synchronizer extracts primary visible content, removes boilerplate such as navigation, headers, footers, cookie text, scripts, and styles, preserves headings, paragraphs, lists, tables, and visible link labels where feasible, then saves a normalized JSON document under:

```text
data/documents/<region>/<source_id>.json
```

Every synchronized chunk includes provenance metadata:

```text
document_id
source_id
source
official_url
region
authority
language
procedure_types
page or section
content_sha256
synchronized_at
source_type
```

### Incremental Reindexing

`ChromaChunkStore.replace_document(...)` replaces only chunks for a changed `document_id`.

New chunks are embedded before old chunks are deleted. If insertion fails, the old chunks remain active. The synchronizer does not rebuild the entire ChromaDB collection for one updated document.

### Candidate Discovery

Discovery runs only from approved landing pages or sources with `discovery_enabled: true`.

It:

- extracts links
- resolves relative URLs
- canonicalizes URLs
- rejects links outside approved domains
- applies include/exclude patterns
- ignores obvious assets
- infers procedure types from deterministic keywords
- deduplicates candidates
- stores candidates in `source_candidates`

Candidates are never indexed automatically.

### CLI

```bash
python -m backend.synchronizer.cli validate
python -m backend.synchronizer.cli sync --all
python -m backend.synchronizer.cli sync --region zh
python -m backend.synchronizer.cli sync --source sem_family_reunification
python -m backend.synchronizer.cli discover --all
python -m backend.synchronizer.cli discover --region vd
python -m backend.synchronizer.cli status
python -m backend.synchronizer.cli candidates list
python -m backend.synchronizer.cli candidates approve <candidate_id>
python -m backend.synchronizer.cli candidates reject <candidate_id> --note "Irrelevant report"
python -m backend.synchronizer.cli cleanup --dry-run
```

Example synchronization report:

```json
{
  "run_id": "8e3f...",
  "requested_scope": "all",
  "status": "completed",
  "checked_count": 2,
  "unchanged_count": 1,
  "updated_count": 1,
  "failed_count": 0,
  "discovered_candidate_count": 0,
  "events": ["zh_driving: updated", "sem_family: unchanged"]
}
```

### Admin Endpoints

Development/admin synchronization endpoints are available only when:

```text
ENABLE_SYNC_ADMIN_ENDPOINTS=true
```

Exposed endpoints:

- `POST /v1/admin/synchronization/run`
- `GET /v1/admin/synchronization/status`
- `GET /v1/admin/synchronization/runs`
- `GET /v1/admin/synchronization/candidates`
- `POST /v1/admin/synchronization/candidates/{candidate_id}/approve`
- `POST /v1/admin/synchronization/candidates/{candidate_id}/reject`

These must not be publicly exposed without authentication. The CLI remains the preferred local control interface.

### Scheduling Preparation

Phase 9 does not embed a scheduler inside FastAPI. External schedulers can call deterministic commands:

```bash
python -m backend.synchronizer.cli sync --all
python -m backend.synchronizer.cli discover --all
```

Suggested cadence:

- approved-source refresh: weekly
- candidate discovery: monthly

Future scheduling can be handled by cron, GitHub Actions, Azure DevOps, or another external scheduler.

### Recovery Behavior

When a source returns `404` or `410`, it is marked unavailable, a failure/event is recorded, and the last successfully indexed version is retained. The synchronizer does not delete local files or ChromaDB chunks because a government website may be temporarily restructured.

## Evaluation Module

Phase 10 Part 1 adds a reusable evaluation architecture, Part 2 adds versioned datasets, and Part 3 adds automated metric calculations. Regression thresholds, before/after reports, and production RAG behavior changes are still intentionally out of scope.

The evaluation module is separate from production code under `evaluation/`. It can inspect stages independently:

- intent classification
- clarification-question generation
- vector retrieval
- BM25 retrieval
- hybrid retrieval
- reranking
- grounded-answer generation
- source citation
- procedure-plan generation
- insufficient-context and abstention behavior
- complete end-to-end execution

### Offline vs Live

Offline mode is the default. It uses stored or mocked outputs and must not call OpenAI or live retrieval/model services unless those dependencies are explicitly injected for a test.

Live mode must be selected explicitly:

```python
EvaluationConfig(execution_mode="live")
```

Live mode is where configured OpenAI models and the local retrieval system can be evaluated later. Phase 10 Part 1 only creates the architecture and safety boundaries.

### Adapters

Evaluation adapters are thin wrappers around existing production services:

- `ClarificationEvaluationAdapter`: runs Phase 4 intent classification and clarification.
- `RetrievalEvaluationAdapter`: runs vector, BM25, and hybrid retrieval independently.
- `RerankingEvaluationAdapter`: runs the Phase 3 reranker over supplied candidates.
- `GenerationEvaluationAdapter`: runs Phase 5 generation in live mode or returns precomputed offline answers.
- `PlannerEvaluationAdapter`: runs Phase 6 planning in live mode or returns precomputed offline plans.
- `EndToEndEvaluationAdapter`: runs the Phase 8 orchestrator through an isolated dependency supplied to evaluation.

The adapters normalize production outputs into `EvaluationCaseResult` without changing production behavior.

### Evaluation Artifacts

Each run writes raw artifacts to:

```text
evaluation/artifacts/<run_id>/
├── run_metadata.json
├── config.json
├── case_results.jsonl
├── case_metrics.jsonl
├── metrics.json
├── aggregate_metrics.json
├── warnings.json
├── errors.json
└── intermediate_outputs/
```

Generated artifacts are ignored by Git by default. The committed `.gitkeep` only preserves the directory.

### Data Isolation

Evaluation runs must not use real user conversations or private data. They must not modify production SQLite or ChromaDB data. Where persistence is needed, tests and future live evaluation should use temporary SQLite/ChromaDB paths or explicitly injected isolated services.

Run metadata records reproducibility details such as:

- run id and run name
- dataset name and version
- execution mode
- timestamp
- Git commit when available
- Python and dependency versions
- evaluation configuration
- retrieval limits and random seed

This prepares the project for regression checks and before/after reporting.

### Automated Metrics

Phase 10 Part 3 keeps metrics separated by pipeline responsibility instead of collapsing everything into one score:

- clarification: intent accuracy, missing-field precision/recall/F1, forbidden-question rate, and completion accuracy.
- retrieval: Recall@K, Precision@K, MRR, MAP, nDCG@K, source coverage, region accuracy, and duplicate rate for vector, BM25, hybrid, and reranked result sets.
- reranking: retained recall, MRR, nDCG, rank improvement, and relevant-evidence drop rate.
- generation: required-fact coverage, forbidden-fact rate, grounded-claim coverage, unsupported-claim rate, answer completeness, and insufficient-context accuracy.
- citations: citation presence, citation coverage, source accuracy, support accuracy, metadata completeness, and fabricated-citation rate.
- abstention: abstention precision/recall, unsafe-answer rate, and unnecessary-abstention rate.
- planning: expected-step coverage, invented-step rate, required-document coverage, invented-document rate, workflow-status accuracy, and unknown-fallback accuracy.
- latency and operations: stage timings, call counts when available, token usage when available, error rate, and completion rate.

Most metrics are deterministic and use structured dataset expectations such as source IDs, relevance judgments, missing fields, expected facts, forbidden facts, and expected workflow statuses. Model-judged or semantic scoring can be added later, but it is not the only source of truth.

Optional RAGAS integration lives behind `evaluation.metrics.optional_ragas`. If RAGAS is not installed or is incompatible, the optional metric reports itself as non-applicable with a warning and does not fail the run. The custom project metrics remain primary.

Aggregate metrics are grouped by metric, category, intent, region, language, nationality category, execution mode, and tags. Non-applicable values are not averaged, and every aggregate includes sample counts so sparse measurements are visible.

### Regression Tests

Phase 10 Part 4 adds automated quality regression checks under `evaluation/regression/` and fast pytest coverage under `tests/regression/`.

Regression checks compare the current evaluation run against three things:

- explicit minimum or maximum thresholds from `evaluation/regression/thresholds.yaml`
- committed baseline summaries from `evaluation/baselines/`
- critical case-specific expectations

The regression layer distinguishes:

- `ThresholdRegression`: the current metric violates an absolute minimum, maximum, or exact-match requirement.
- `BaselineRegression`: the current metric degrades beyond an allowed absolute or relative difference from the committed baseline.
- `CriticalCaseRegression`: a protected case fails a required metric.
- `SafetyRegression`: unsafe behavior appears, such as unsupported claims, fabricated citations, unsafe answers despite insufficient evidence, forbidden clarification questions, or invented planner requirements.
- `PerformanceRegression`: latency, error rate, or completion behavior degrades beyond limits.
- `DatasetCompatibilityChange`: the dataset, source registry, or knowledge-base fingerprint changed, so baseline comparison has limited comparability.

Threshold rules support metric direction:

```yaml
retrieval:
  hybrid_recall_at_k_10:
    direction: higher_is_better
    minimum: 0.80
    max_absolute_drop: 0.03

generation:
  unsupported_claim_rate:
    direction: lower_is_better
    maximum: 0.05
    max_absolute_increase: 0.02
```

Knowledge-base fingerprints are deterministic summaries built from available local metadata: source-registry version, enabled source IDs, local document hashes, document IDs, and optional ChromaDB collection metadata. When the fingerprint differs from the baseline, the regression report marks comparison context as `limited_comparability`. Thresholds are still enforced, but metric movement is not silently treated as purely a code regression.

Committed baselines are summaries only. They must not contain private model outputs, full conversations, personal user data, or full generated answers. New baselines are created through `BaselineGenerationService.create_baseline(...)`, require a human approval note, and refuse to overwrite existing baseline files unless `force=True` is explicitly supplied. Baselines must never update automatically just because a regression test failed.

Run the fast offline regression tests:

```bash
.venv/bin/python -m pytest tests/regression
```

Live regression tests are marked with `@pytest.mark.live_evaluation` and are skipped by default. Enable them explicitly only when live model/retrieval calls are intended:

```bash
RUN_LIVE_EVALUATION=1 .venv/bin/python -m pytest -m live_evaluation
```

### Evaluation CLI and Reports

Phase 10 Part 5 adds a developer CLI:

```bash
python -m evaluation.cli validate-datasets
python -m evaluation.cli run --dataset smoke/v1 --mode offline
python -m evaluation.cli run --dataset retrieval/v1 --mode live --tag immigration --yes
python -m evaluation.cli compare --before <run_id_or_path> --after <run_id_or_path>
python -m evaluation.cli compare --baseline retrieval_v1 --after <run_id_or_path>
python -m evaluation.cli baseline create --run <run_id_or_path> --name retrieval_v2 --approval-note "Approved after source-registry expansion"
python -m evaluation.cli list-runs
python -m evaluation.cli show-run <run_id_or_path>
python -m evaluation.cli report <run_id_or_path> --format html
```

Evaluation run options include:

```text
--dataset
--mode offline|live
--case-id
--tag
--max-cases
--run-name
--output-dir
--save-intermediate
--generation
--planner
--judge-model
--fail-fast
--seed
--config
--notes
```

Live mode prints a clear warning and refuses to run unless `--yes` is supplied because API-backed evaluations may incur costs.

Before/after comparisons are handled by `evaluation/comparison/`. The comparator inspects:

- aggregate metrics
- metric categories
- case-level results
- latency
- errors
- model configuration
- prompt hashes when available
- knowledge-base fingerprint
- source-registry version when available

Report output is written under:

```text
evaluation/reports/<comparison_id>/
├── comparison.json
├── comparison.md
├── comparison.html
└── report_metadata.json
```

The JSON report is machine-readable. The Markdown report is suitable for pull requests. The HTML report is a standalone local file with an executive summary, metric tables, simple charts, critical failures, latency comparison, configuration comparison, warnings, and rule-based investigation recommendations.

Rule-based recommendations are deterministic. Examples:

- Hybrid Recall@10 decreased while BM25 stayed stable: inspect vector embeddings, metadata filters, or ChromaDB document replacement.
- Citation quality decreased: inspect source serialization, cited source IDs, and the grounded generation prompt.
- Unsafe-answer rate increased: inspect insufficient-context handling and abstention logic.
- Reranking latency increased: inspect CrossEncoder loading, batching, and candidate count.
- Clarification recall decreased: inspect deterministic procedure schemas and required-field definitions.

CLI exit codes:

```text
0 = passed
1 = regression failure
2 = configuration or dataset error
3 = execution failure
4 = baseline incompatibility requiring review
```

Example development workflow:

1. Run the baseline evaluation.
2. Make a retrieval, prompt, document, or planner change.
3. Run the same dataset again.
4. Compare before and after.
5. Inspect regressions and warnings.
6. Approve a new baseline only when the change is intentional and validated.

Current Phase 10 evaluation architecture:

```text
Swiss Lawyer MCP pipeline
↓
Evaluation adapters
↓
Versioned datasets
↓
Automated metrics
↓
Regression checks
↓
Before/after comparison
↓
JSON, Markdown and HTML reports
↓
Future CI quality gate
```

## Evaluation Datasets

Phase 10 Part 2 adds versioned JSONL datasets under:

```text
evaluation/datasets/
```

Dataset groups:

- `smoke/v1.jsonl`: 10 representative cases for quick runner checks.
- `clarification/v1.jsonl`: 20 cases for intent and missing-field behavior.
- `retrieval/v1.jsonl`: 25 cases for federal, Zurich canton, keyword, semantic, multilingual, and unsupported retrieval.
- `generation/v1.jsonl`: 15 cases using synthetic retrieved-context fixtures and fact-level expectations.
- `planning/v1.jsonl`: 10 cases for workflow concepts, statuses, documents, and unsupported-invention checks.
- `end_to_end/v1.jsonl`: 15 realistic scenarios covering non-EU/EFTA, EU/EFTA, UK, Swiss permit holders, memory continuation, unsupported topics, ambiguous cities, and insufficient context.

Every JSONL file starts with a metadata record containing:

```text
name
version
created_at
description
source_registry_version
applicable_knowledge_base_version
authoring_notes
```

Cases use structured expectations instead of exact answer strings. Expected and forbidden answer facts are paraphrased records with `fact_id`, `description`, `importance`, and optional `required_source_ids`.

Retrieval cases support graded relevance:

```text
0 = irrelevant
1 = partially relevant
2 = relevant
3 = highly relevant
```

Coverage status distinguishes:

- `supported`: current seed documents should support the case.
- `insufficient_context`: the correct behavior is to abstain or say context is insufficient.
- `future_coverage`: supported by architecture but not current indexed seed evidence.
- `synchronizer_coverage`: expected to become supported after approved source synchronization.

Validate datasets:

```bash
python -m evaluation.datasets.validator
```

Do not silently modify an existing dataset version when expectations materially change. Create a new file such as `v2.jsonl` and update its metadata.

## Local Mode Details

The current development default is fully local:

```text
ChatGPT
↓
ngrok
↓
http://127.0.0.1:8001/mcp
↓
Docker Compose MCP container
↓
Docker Compose FastAPI container
↓
Ollama on the macOS host
```

Local AI configuration:

```text
AI_MODE=local
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
GENERATION_PROVIDER=ollama
GENERATION_MODEL=llama3.2
PLANNER_PROVIDER=ollama
PLANNER_MODEL=llama3.2
RERANKER_PROVIDER=disabled
```

In this mode the app does not require `OPENAI_API_KEY` and does not initialize OpenAI clients. Embeddings use Ollama `/api/embed`, answer generation and planning use Ollama `/api/chat`, and reranking is disabled so Docker does not install `sentence-transformers`, PyTorch, CUDA, or NVIDIA packages.

Use the setup and startup scripts from the Quick Start section at the top of this README.

For native Python commands, use:

```text
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

Inside Docker, the API container uses:

```text
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

Test retrieval locally:

```bash
python -m backend.retrieval.test_retrieval "Can a Brazilian citizen work in Switzerland?"
```

Test reranking schema locally:

```bash
python -m backend.reranking.test_reranker "Can a Brazilian citizen work in Switzerland?"
```

With `RERANKER_PROVIDER=disabled`, the reranker preserves the Phase 3 output schema and copies hybrid retrieval scores as rerank scores. This is intentionally lightweight for the first local MCP portfolio test.

ChatGPT connects through ngrok using the HTTPS forwarding URL ending in `/mcp`. Choose no authentication in the ChatGPT MCP app. This is a private local portfolio architecture, not a public multi-user deployment.

`llama3.2` is sufficient for a functional portfolio test, but the generated output remains procedural guidance only and not legal advice.

## Run Tests

```bash
.venv/bin/pytest
```
