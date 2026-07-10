# Swiss Lawyer MCP

Swiss Lawyer MCP is a production-minded Agentic RAG backend for informational guidance about Swiss immigration and administrative procedures. The system is designed to use official Swiss government sources only, preserve evidence metadata, and later expose grounded procedure support through an MCP tool.

This repository currently implements **Phase 1: PDF ingestion**, **Phase 2: hybrid retrieval**, **Phase 3: reranking**, **Phase 4.2: schema-driven clarification**, **Phase 5: grounded answer generation**, **Phase 6: planner/workflow engine**, and **Phase 7: SQLite memory**. It does not yet implement FastAPI, synchronization, or MCP integration.

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
│       └── 0001_phase_7_memory.py
├── pytest.ini
├── requirements.txt
├── backend/
│   ├── __init__.py
│   ├── api/
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
├── notebooks/
└── tests/
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

Only Phase 1 ingestion, Phase 2 retrieval, Phase 3 reranking, Phase 4.2 clarification, Phase 5 grounded generation, Phase 6 planning, and Phase 7 memory are implemented right now. Some backend folders such as `api/` and `synchronizer/` already exist as placeholders for later phases. Generated folders such as `__pycache__/`, `.pytest_cache/`, `.venv/`, generated ChromaDB files, and the generated SQLite database are intentionally omitted from this tree.

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
