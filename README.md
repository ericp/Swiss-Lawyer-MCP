# Swiss Lawyer MCP

Swiss Lawyer MCP is a production-minded Agentic RAG backend for informational guidance about Swiss immigration and administrative procedures. The system is designed to use official Swiss government sources only, preserve evidence metadata, and later expose grounded procedure support through an MCP tool.

This repository currently implements **Phase 1: PDF ingestion**, **Phase 2: hybrid retrieval**, **Phase 3: reranking**, **Phase 4.2: schema-driven clarification**, **Phase 5: grounded answer generation**, **Phase 6: planner/workflow engine**, **Phase 7: SQLite memory**, **Phase 8: FastAPI orchestration**, **Phase 9: official source synchronization**, **Phase 10 Part 1: evaluation module architecture**, **Phase 10 Part 2: versioned evaluation datasets**, **Phase 10 Part 3: automated evaluation metrics**, and **Phase 10 Part 4: automated quality regression tests**. It does not yet implement MCP integration, OAuth, a frontend, cloud deployment, GitHub Actions scheduling, the final comparison CLI/formatted report, or mandatory RAGAS evaluation.

## Safety Scope

This project is not a legal adviser. It provides informational guidance only and must ground future answers in retrieved official-source evidence.

## Folder Structure

```text
Swiss Lawyer MCP/
├── .env.example
├── .gitignore
├── README.md
├── alembic.ini
├── docker-compose.yml
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 0001_phase_7_memory.py
│       └── 0002_phase_9_synchronizer.py
├── pytest.ini
├── requirements.txt
├── backend/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── app.py
│   │   ├── dependencies.py
│   │   ├── error_handlers.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── admin_synchronization.py
│   │   │   ├── health.py
│   │   │   └── procedures.py
│   │   └── schemas.py
│   ├── clarification/
│   │   ├── __init__.py
│   │   ├── clarification_engine.py
│   │   ├── intent_classifier.py
│   │   ├── procedure_schemas.py
│   │   └── test_clarification.py
│   ├── generation/
│   │   ├── __init__.py
│   │   ├── answer_generator.py
│   │   ├── confidence.py
│   │   ├── prompts.py
│   │   ├── source_attribution.py
│   │   └── test_generation.py
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── chunking.py
│   │   ├── discovery.py
│   │   ├── embeddings.py
│   │   ├── extraction.py
│   │   ├── index.py
│   │   └── vector_store.py
│   ├── location/
│   │   ├── __init__.py
│   │   └── canton_resolver.py
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── memory_service.py
│   │   ├── models.py
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── converters.py
│   │   │   ├── interaction_repository.py
│   │   │   ├── procedure_repository.py
│   │   │   ├── profile_repository.py
│   │   │   └── user_repository.py
│   │   └── test_memory.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── chunk.py
│   │   ├── clarification.py
│   │   ├── document.py
│   │   ├── generation.py
│   │   ├── memory.py
│   │   ├── planner.py
│   │   ├── reranking.py
│   │   ├── retrieval.py
│   │   └── user_profile.py
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   └── procedure_orchestrator.py
│   ├── planners/
│   │   ├── __init__.py
│   │   ├── prompts.py
│   │   ├── test_planner.py
│   │   └── workflow_planner.py
│   ├── prompts/
│   │   ├── grounded_answer_system_prompt.txt
│   │   └── workflow_planner_system_prompt.txt
│   ├── reranking/
│   │   ├── __init__.py
│   │   ├── reranker.py
│   │   ├── reranking_service.py
│   │   └── test_reranker.py
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── bm25.py
│   │   ├── hybrid.py
│   │   ├── test_retrieval.py
│   │   └── vector.py
│   ├── synchronizer/
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   ├── discovery.py
│   │   ├── document_processor.py
│   │   ├── hashing.py
│   │   ├── html_extraction.py
│   │   ├── http_client.py
│   │   ├── identifiers.py
│   │   ├── models.py
│   │   ├── regions.py
│   │   ├── repository.py
│   │   ├── source_registry.py
│   │   └── synchronizer_service.py
│   └── utils/
│       ├── __init__.py
│       └── config.py
├── data/
│   ├── chromadb/
│   │   └── .gitkeep
│   ├── pdfs/
│   │   ├── be/
│   │   ├── federal/
│   │   ├── ge/
│   │   ├── metadata/
│   │   │   └── sources.yaml
│   │   ├── vd/
│   │   └── zh/
│   └── sqlite/
│       └── .gitkeep
├── docs/
├── evaluation/
│   ├── __init__.py
│   ├── config.py
│   ├── models.py
│   ├── runner.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── clarification_adapter.py
│   │   ├── common.py
│   │   ├── end_to_end_adapter.py
│   │   ├── generation_adapter.py
│   │   ├── planner_adapter.py
│   │   ├── reranking_adapter.py
│   │   └── retrieval_adapter.py
│   ├── artifacts/
│   ├── baselines/
│   │   ├── README.md
│   │   ├── clarification_v1.json
│   │   ├── end_to_end_v1.json
│   │   ├── generation_v1.json
│   │   ├── planning_v1.json
│   │   ├── retrieval_v1.json
│   │   └── smoke_v1.json
│   ├── datasets/
│   │   ├── README.md
│   │   ├── __init__.py
│   │   ├── loader.py
│   │   ├── validator.py
│   │   ├── schemas/
│   │   │   └── evaluation_case.schema.json
│   │   ├── smoke/
│   │   │   └── v1.jsonl
│   │   ├── clarification/
│   │   │   └── v1.jsonl
│   │   ├── retrieval/
│   │   │   └── v1.jsonl
│   │   ├── generation/
│   │   │   └── v1.jsonl
│   │   ├── planning/
│   │   │   └── v1.jsonl
│   │   ├── end_to_end/
│   │   │   └── v1.jsonl
│   │   └── fixtures/
│   ├── metrics/
│   │   ├── __init__.py
│   │   ├── abstention.py
│   │   ├── aggregate.py
│   │   ├── base.py
│   │   ├── citations.py
│   │   ├── clarification.py
│   │   ├── generation.py
│   │   ├── latency.py
│   │   ├── optional_ragas.py
│   │   ├── planning.py
│   │   ├── reranking.py
│   │   └── retrieval.py
│   ├── regression/
│   │   ├── __init__.py
│   │   ├── baseline_service.py
│   │   ├── baselines.py
│   │   ├── checker.py
│   │   ├── fingerprint.py
│   │   ├── models.py
│   │   ├── thresholds.py
│   │   └── thresholds.yaml
│   └── reports/
├── notebooks/
└── tests/
    ├── evaluation/
    │   ├── test_datasets.py
    │   ├── test_evaluation_module.py
    │   └── test_metrics.py
    ├── regression/
    │   ├── conftest.py
    │   ├── helpers.py
    │   ├── test_citation_quality.py
    │   ├── test_clarification_quality.py
    │   ├── test_generation_safety.py
    │   ├── test_planner_quality.py
    │   ├── test_retrieval_quality.py
    │   └── test_smoke_quality.py
    ├── test_answer_generator.py
    ├── test_bm25_retrieval.py
    ├── test_clarification_engine.py
    ├── test_chunking.py
    ├── test_discovery.py
    ├── test_embeddings.py
    ├── test_extraction.py
    ├── test_generation_models.py
    ├── test_generation_prompts.py
    ├── test_hybrid_retrieval.py
    ├── test_index.py
    ├── test_intent_classifier.py
    ├── test_memory_service.py
    ├── test_phase8_api_orchestration.py
    ├── test_phase9_synchronizer.py
    ├── test_planner_models.py
    ├── test_reranker.py
    ├── test_reranking_models.py
    ├── test_reranking_service.py
    ├── test_retrieval_models.py
    ├── test_source_attribution.py
    ├── test_user_profile.py
    ├── test_vector_retrieval.py
    ├── test_vector_store.py
    └── test_workflow_planner.py
```

Phase 1 ingestion through Phase 10 Part 4 automated quality regression tests are implemented right now. Generated folders such as `__pycache__/`, `.pytest_cache/`, `.venv/`, generated ChromaDB files, generated evaluation artifacts, synchronized normalized webpage files, temporary downloads, and the generated SQLite database are intentionally omitted from this tree.

The `data/pdfs/` directory contains regional subfolders such as `federal`, `zh`, `ge`, `vd`, and `be`. The ingestion pipeline uses each PDF's parent folder as its region metadata.

## Setup

Use Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Export `OPENAI_API_KEY` in your shell before running ingestion. The `.env.example` file documents the expected variables for local setup.

## Environment Variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | empty | Required for OpenAI embeddings |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `PDF_ROOT` | `data/pdfs` | Root folder scanned recursively for PDFs |
| `CHROMA_PATH` | `data/chromadb` | Persistent ChromaDB storage path |
| `CHROMA_COLLECTION` | `swiss_procedures` | ChromaDB collection name |
| `CHUNK_SIZE_WORDS` | `600` | Chunk size in words |
| `CHUNK_OVERLAP_WORDS` | `100` | Word overlap between adjacent chunks |
| `RETRIEVAL_TOP_K` | `10` | Default number of candidates returned by each retrieval method |
| `RERANK_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Local Sentence Transformers CrossEncoder model |
| `RERANK_TOP_K` | `5` | Number of reranked chunks selected from merged candidates |
| `OPENAI_GENERATION_MODEL` | `gpt-4o-mini` | OpenAI GPT model used for grounded answer generation |
| `OPENAI_PLANNER_MODEL` | `gpt-4o-mini` | OpenAI GPT model used for workflow planning |
| `API_HOST` | `127.0.0.1` | Local FastAPI host |
| `API_PORT` | `8000` | Local FastAPI port |
| `SQLITE_DATABASE_URL` | `sqlite:///data/sqlite/memory.db` | SQLAlchemy database URL for user memory |
| `REQUEST_TIMEOUT_SECONDS` | `60` | Request timeout budget for API clients and future callers |
| `LOG_LEVEL` | `INFO` | API logging level |
| `ENABLE_SYNC_ADMIN_ENDPOINTS` | `false` | Enables development-only synchronization admin endpoints |
| `SYNC_SOURCE_REGISTRY_PATH` | `data/pdfs/metadata/sources.yaml` | Curated source registry path |
| `SYNC_PDF_PATH` | `data/pdfs` | Local storage root for synchronized PDFs |
| `SYNC_DOCUMENT_PATH` | `data/documents` | Local storage root for normalized webpage documents |
| `SYNC_TEMP_DOWNLOAD_PATH` | `data/tmp/synchronizer` | Temporary download location |
| `SYNC_HTTP_TIMEOUT_SECONDS` | `30` | HTTP timeout for synchronization requests |
| `SYNC_MAX_DOCUMENT_BYTES` | `20000000` | Maximum downloaded document size |
| `SYNC_RETRY_COUNT` | `2` | Retry count for temporary HTTP failures |
| `SYNC_RETRY_BACKOFF_SECONDS` | `0.25` | Exponential retry backoff base |
| `SYNC_USER_AGENT` | `Swiss Lawyer MCP Synchronizer/0.9` | Synchronizer HTTP user agent |
| `SYNC_RETAIN_UNAVAILABLE_SOURCES` | `true` | Retain last valid indexed version when a source is unavailable |
| `SYNC_CANDIDATE_DISCOVERY_ENABLED` | `true` | Enable candidate discovery commands |
| `SYNC_WEBPAGE_MIN_CONTENT_CHARS` | `100` | Minimum extracted webpage content target |

## Storage Roles

Swiss Lawyer MCP uses two separate storage systems:

- **ChromaDB** stores official Swiss knowledge and document chunks.
- **SQLite** stores user-specific memory: profile facts, saved procedures, progress, and concise summaries.

Keeping these stores separate prevents user memory from mixing with the legal/procedural knowledge base.

## Run Ingestion

```bash
export OPENAI_API_KEY="your-api-key"
python -m backend.ingestion.index
```

The command scans `data/pdfs/`, extracts text page by page with PyMuPDF, chunks extracted text, generates OpenAI embeddings, and writes the chunks into the persistent ChromaDB collection `swiss_procedures`.

## Hybrid Retrieval

Phase 2 retrieves candidate chunks from the existing ChromaDB collection using two methods:

- **Vector search** embeds the user question with `text-embedding-3-small` and queries ChromaDB for semantically similar chunks.
- **BM25 keyword search** loads all stored ChromaDB chunks, tokenizes their text, builds a `rank-bm25` index, and scores chunks against the user's query terms.

The `HybridRetriever` runs both methods, merges the results, removes duplicate chunk IDs, and preserves retrieval source information. It does not rerank and does not generate answers.

## Reranking

Hybrid retrieval is good at recall: vector search can find semantically similar chunks, while BM25 can catch exact keyword matches. It can still return candidates that are only loosely related to the question. Reranking improves precision by scoring each merged candidate directly against the question.

Phase 3 uses a local Sentence Transformers CrossEncoder:

```text
cross-encoder/ms-marco-MiniLM-L-6-v2
```

For each candidate, the reranker scores the pair:

```text
(question, chunk text)
```

The reranker sorts candidates by CrossEncoder relevance score and keeps the top results. It does not call external APIs and does not generate answers.

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

Grounded generation uses a reusable system prompt stored in `backend/prompts/grounded_answer_system_prompt.txt`. The prompt instructs the GPT model to answer only from supplied official context, never invent rules, documents, deadlines, authorities, or procedures, and explicitly say when retrieved context is insufficient.

The generated answer is structured as:

- short direct answer
- explanation
- procedure steps
- important notes
- cited official sources
- deterministic confidence label
- insufficient-context flag

If no reranked context is available, the generator does not call OpenAI. It returns:

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
export OPENAI_API_KEY="your-api-key"
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
export OPENAI_API_KEY="your-api-key"
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

Current Phase 8 architecture:

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

### Endpoints

- `GET /health`: checks application, SQLite, ChromaDB, and OpenAI configuration availability.
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

### Supported Regions

The synchronizer supports `federal` plus all 26 Swiss cantons:

```text
ag ai ar be bl bs fr ge gl gr ju lu ne nw ow sg sh so sz tg ti ur vd vs zg zh
```

Region names and approved government domains live centrally in `backend/synchronizer/regions.py`. Domain rules are not scattered across the codebase.

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

This prepares the project for regression thresholds and before/after reporting in later Phase 10 work.

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

## Test Retrieval

```bash
export OPENAI_API_KEY="your-api-key"
python -m backend.retrieval.test_retrieval "Can a Brazilian citizen work in Switzerland?"
```

The command prints vector results, BM25 results, and the merged candidate list with metadata and scores.

## Test Reranking

```bash
export OPENAI_API_KEY="your-api-key"
python -m backend.reranking.test_reranker "Can a Brazilian citizen work in Switzerland?"
```

The command prints merged retrieval candidates followed by reranked results with source file, region, retrieval source, retrieval score, and rerank score.

## Run Tests

```bash
.venv/bin/pytest
```
