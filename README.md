# Swiss Lawyer MCP

Swiss Lawyer MCP is a production-minded Agentic RAG backend for informational guidance about Swiss immigration and administrative procedures. The system is designed to use official Swiss government sources only, preserve evidence metadata, and later expose grounded procedure support through an MCP tool.

This repository currently implements **Phase 1: PDF ingestion**, **Phase 2: hybrid retrieval**, **Phase 3: reranking**, **Phase 4.2: schema-driven clarification**, and **Phase 5: grounded answer generation**. It does not yet implement memory, planning, FastAPI, synchronization, or MCP integration.

## Safety Scope

This project is not a legal adviser. It provides informational guidance only and must ground future answers in retrieved official-source evidence.

## Folder Structure

```text
Swiss Lawyer MCP/
├── .env.example
├── .gitignore
├── README.md
├── docker-compose.yml
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
│   ├── models/
│   │   ├── __init__.py
│   │   ├── chunk.py
│   │   ├── clarification.py
│   │   ├── document.py
│   │   ├── generation.py
│   │   ├── reranking.py
│   │   ├── retrieval.py
│   │   └── user_profile.py
│   ├── planners/
│   ├── prompts/
│   │   └── grounded_answer_system_prompt.txt
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
    ├── test_reranker.py
    ├── test_reranking_models.py
    ├── test_reranking_service.py
    ├── test_retrieval_models.py
    ├── test_source_attribution.py
    ├── test_user_profile.py
    ├── test_vector_retrieval.py
    └── test_vector_store.py
```

Only Phase 1 ingestion, Phase 2 retrieval, Phase 3 reranking, Phase 4.2 clarification, and Phase 5 grounded generation are implemented right now. Some backend folders such as `api/`, `memory/`, and `synchronizer/` already exist as placeholders for later phases. Generated folders such as `__pycache__/`, `.pytest_cache/`, `.venv/`, and generated ChromaDB files are intentionally omitted from this tree.

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
