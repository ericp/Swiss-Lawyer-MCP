# Swiss Lawyer MCP

Swiss Lawyer MCP is a production-minded Agentic RAG backend for informational guidance about Swiss immigration and administrative procedures. The system is designed to use official Swiss government sources only, preserve evidence metadata, and later expose grounded procedure support through an MCP tool.

This repository currently implements **Phase 1: PDF ingestion**, **Phase 2: hybrid retrieval**, and **Phase 3: reranking**. It does not yet implement memory, planning, answer generation, FastAPI, synchronization, or MCP integration.

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
│   ├── generation/
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
│   │   ├── document.py
│   │   ├── reranking.py
│   │   └── retrieval.py
│   ├── planners/
│   ├── prompts/
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
    ├── test_bm25_retrieval.py
    ├── test_chunking.py
    ├── test_discovery.py
    ├── test_embeddings.py
    ├── test_extraction.py
    ├── test_hybrid_retrieval.py
    ├── test_index.py
    ├── test_reranker.py
    ├── test_reranking_models.py
    ├── test_reranking_service.py
    ├── test_retrieval_models.py
    ├── test_vector_retrieval.py
    └── test_vector_store.py
```

Only Phase 1 ingestion, Phase 2 retrieval, and Phase 3 reranking are implemented right now. Some backend folders such as `api/`, `memory/`, and `synchronizer/` already exist as placeholders for later phases. Generated folders such as `__pycache__/`, `.pytest_cache/`, `.venv/`, and generated ChromaDB files are intentionally omitted from this tree.

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
