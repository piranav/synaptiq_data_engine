# Synaptiq - Your Knowledge Rolodex

Synaptiq is a personal knowledge management system that transforms scattered information into an interconnected knowledge graph. Ingest content from various sources, let AI extract and connect concepts, then chat with your knowledge using natural language.

## ✨ Features

### 🧠 Knowledge Graph
- **Semantic storage** using RDF/OWL with Apache Fuseki
- **Automatic concept extraction** and relationship mapping via GPT agents
- **Interactive graph visualization** with Poincaré disk hyperbolic mapping
- **SPARQL queries** generated from natural language

### 📥 Multi-Source Ingestion
- **YouTube videos** — transcripts with timestamps
- **Web articles** — scraped and cleaned content
- **PDF & DOCX files** — document parsing and extraction
- **Notes** — markdown notes with rich text editing

### 🤖 AI-Powered Chat
- **Chat with your knowledge** using multi-agent orchestration
- **Intent classification** for query routing (factual, exploratory, comparative)
- **Hybrid retrieval** — knowledge graph + vector search with intelligent fallbacks
- **Source citations** with clickable links and timestamps

### 📝 Notes System
- **Markdown editor** with live preview
- **Auto-linking** to concepts in your knowledge graph
- **Folder organization** with drag-and-drop
- **Mermaid diagram support** for visual notes

### 🔍 Semantic Search
- **Vector similarity search** via Qdrant
- **Chunked documents** with semantic boundaries
- **OpenAI embeddings** for high-quality retrieval

## 🏗 Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (Next.js)                               │
│   Dashboard │ Chat │ Notes │ Graph Visualization │ Sources │ Settings      │
└─────────────────────────────────┬──────────────────────────────────────────┘
                                  │ REST + WebSocket
                                  ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                          API LAYER (FastAPI)                               │
│  /auth │ /chat │ /notes │ /graph │ /ingest │ /search │ /sources │ /user   │
└─────────────┬────────────────────────────────────────────────────┬─────────┘
              │                                                    │
              ▼                                                    ▼
┌─────────────────────────────┐    ┌─────────────────────────────────────────┐
│       AGENT LAYER           │    │            INGESTION PIPELINE           │
│  ┌─────────────────────┐    │    │  YouTubeAdapter ─┐                      │
│  │ Query Orchestrator  │    │    │  WebAdapter      ├─→ Chunker → Extractor│
│  │  • Intent Classifier│    │    │  DocAdapter      │                      │
│  │  • SPARQL Agent     │    │    │  NotesAdapter   ─┘          ↓           │
│  │  • Response Synth   │    │    │               EmbeddingGenerator        │
│  └─────────────────────┘    │    └─────────────────────────────────────────┘
└─────────────┬───────────────┘                    │
              │                                    │
              ▼                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                          STORAGE LAYER                                     │
│  Apache Fuseki (RDF)  │  Qdrant (Vectors)  │  PostgreSQL (Users/Sessions)  │
└────────────────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- OpenAI API key

### 1. Clone & Install

```bash
git clone https://github.com/yourusername/synaptiq.git
cd synaptiq

# Backend
pip install -r requirements.txt

# Frontend
cd frontend && npm install && cd ..
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

Required environment variables:
| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key for embeddings & agents |
| `SUPADATA_API_KEY` | Supadata API for YouTube transcripts |
| `QDRANT_URL` | Qdrant Cloud or local URL |
| `QDRANT_API_KEY` | Qdrant API key |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis URL for Celery background tasks |
| `FUSEKI_URL` | Apache Fuseki SPARQL endpoint |

### 3. Start Services

```bash
# Start infrastructure (Redis, Fuseki, etc.)
docker-compose up -d

# Start API server
uvicorn synaptiq.api.app:app --reload

# Start Celery worker (for background ingestion)
celery -A synaptiq.workers.celery_app worker --loglevel=info

# Start frontend
cd frontend && npm run dev
```

### 4. Access the App

- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## 📡 API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/signup` | Create account |
| POST | `/api/v1/auth/login` | Get access/refresh tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |

### Knowledge Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/ingest` | Ingest URL (YouTube/article) |
| POST | `/ingest/upload` | Upload file (PDF/DOCX) |
| POST | `/search` | Semantic search |
| GET | `/sources` | List ingested sources |

### Chat & Graph
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat` | Query your knowledge |
| GET | `/chat/sessions` | List chat sessions |
| GET | `/graph` | Get knowledge graph data |
| GET | `/graph/concepts/{id}` | Get concept details |

### Notes
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/notes` | List all notes |
| POST | `/notes` | Create note |
| PUT | `/notes/{id}` | Update note |
| DELETE | `/notes/{id}` | Delete note |

### WebSocket
| Endpoint | Description |
|----------|-------------|
| `/ws?token=<jwt>` | Real-time updates for jobs, chat streaming |

## 🧩 Tech Stack

**Backend**
- FastAPI (async Python web framework)
- OpenAI Agents SDK (multi-agent orchestration)
- Apache Fuseki (RDF triple store + SPARQL)
- Qdrant (vector database)
- PostgreSQL + SQLAlchemy (relational data)
- Celery + Redis (background jobs)
- SUPADATA - for extraction

**Frontend**
- Next.js 14 (React framework)
- TypeScript
- CSS Modules with glassmorphism design

**AI/ML**
- OpenAI and Anthropic (agents & chat)
- OpenAI text-embedding-3-small (embeddings)
- LangChain (concept extraction)

## 📖 Core Concepts

### Knowledge Representation
Synaptiq uses an RDF ontology (`synaptiq.ttl`) to represent:
- **Concepts** — key ideas extracted from content
- **Claims** — factual statements about relationships
- **Sources** — origin of information with provenance
- **Notes** — user-created markdown content

### Multi-Agent Architecture
The query pipeline uses specialized agents:
1. **Intent Classifier** — determines query type
2. **SPARQL Agent** — generates graph queries from natural language
3. **Response Synthesizer** — crafts answers with citations

### Retrieval Strategy
Hybrid approach with fallbacks:
1. Try knowledge graph (SPARQL) → structured relationships
2. Fall back to vector search (Qdrant) → semantic similarity
3. Enrich with cross-references between sources

## 🛠 Development

### Project Structure

```
synaptiq/
├── src/synaptiq/
│   ├── adapters/       # Source-specific ingestion
│   ├── agents/         # AI query agents
│   ├── api/            # FastAPI routes & middleware
│   ├── ontology/       # RDF schema & graph manager
│   ├── processors/     # Chunking, extraction, embeddings
│   ├── services/       # Business logic
│   ├── storage/        # Database clients
│   └── workers/        # Celery background tasks
├── frontend/
│   ├── src/app/        # Next.js pages
│   ├── src/components/ # React components
│   └── src/lib/        # Services & utilities
├── config/             # Settings & configuration
└── docker-compose.yml  # Infrastructure services
```

### Running Tests

```bash
pytest tests/ -v
```

### Database Migrations

```bash
alembic upgrade head
```

## 📄 License

MIT

---

Built with ❤️ for knowledge seekers
