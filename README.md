# Synaptiq Data Engine

A production-grade data processing pipeline for personal knowledge management. Ingests content from YouTube videos, web articles, and notes, processes them through semantic chunking and embedding generation, and stores them in Qdrant for vector search.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      INGESTION LAYER                            │
│  YouTube Videos → YouTubeAdapter  ─┐                            │
│  Web Articles   → WebAdapter       ├─→ CanonicalDocument        │
│  Notes          → NotesAdapter     ─┘                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      PROCESSING LAYER                           │
│  SemanticChunker → ConceptExtractor (LLM) → EmbeddingGenerator  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       STORAGE LAYER                             │
│         Qdrant (vectors)  ←→  MongoDB (metadata)                │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys and connection strings
```

### 3. Start Redis (for Celery)

```bash
docker-compose up -d redis
```

### 4. Start the API Server

```bash
uvicorn synaptiq.api.app:app --reload
```

### 5. Start Celery Worker

```bash
celery -A synaptiq.workers.celery_app worker --loglevel=info
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/ingest` | Queue a URL for ingestion |
| GET | `/jobs/{job_id}` | Check job status |
| POST | `/search` | Vector search with filters |
| GET | `/sources` | List ingested sources |

## CLI Commands

```bash
# Ingest a YouTube video
python -m synaptiq.cli ingest https://youtube.com/watch?v=...

# Ingest a web article
python -m synaptiq.cli ingest https://example.com/article

# Search your knowledge base
python -m synaptiq.cli search "What is a tensor?"

# List all sources
python -m synaptiq.cli sources --user-id your_user_id
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SUPADATA_API_KEY` | SUPADATA API key | Yes |
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `QDRANT_URL` | Qdrant Cloud URL | Yes |
| `QDRANT_API_KEY` | Qdrant API key | Yes |
| `MONGODB_URI` | MongoDB connection string | Yes |
| `REDIS_URL` | Redis URL for Celery | Yes |

## Extending the Pipeline

### Adding a New Source Adapter

1. Create a new adapter in `src/synaptiq/adapters/`
2. Inherit from `BaseAdapter`
3. Implement `async def ingest(url: str, user_id: str) -> CanonicalDocument`
4. Register in `AdapterFactory`

### Adding a New Processor

1. Create a new processor in `src/synaptiq/processors/`
2. Implement the `Processor` protocol
3. Add to the pipeline chain

## License

MIT


