# RAG Pipeline

Owned by whoever is assigned `apps/chatbot/` (see `TASK_DIVISION.md`).
Lives entirely under `backend/apps/chatbot/`.

## Files

| File                          | Responsibility                                                       |
|--------------------------------|-----------------------------------------------------------------------|
| `rag/embeddings.py`            | One function wrapping the embedding model — nothing else touches the vendor SDK directly |
| `rag/ingest.py`                | Loads products + business info → chunks → embeds → stores in pgvector |
| `rag/retriever.py`              | Embeds a question, does a similarity search, returns top-k chunks     |
| `rag/generator.py`              | Builds the grounded prompt, calls the LLM, returns the answer         |
| `management/commands/ingest_knowledge_base.py` | CLI: `python manage.py ingest_knowledge_base`         |
| `models.py`                    | `KnowledgeChunk` model (source type, source id, text, embedding vector, metadata) |
| `views.py`                     | `POST /api/chatbot/ask/` — wires retriever → generator → response     |

## Data that gets embedded

- Every product: name, description, price, specs → one or more chunks.
- Business info entered via Django admin: return policy, delivery info,
  store locations, FAQs → stored as their own model, chunked the same way.

## Ingestion flow

```
Product / BusinessInfo rows
        │
        ▼
  chunk into ~200-400 token pieces
        │
        ▼
  embed each chunk (embeddings.py)
        │
        ▼
  upsert into KnowledgeChunk (pgvector column)
```

Run after any bulk data change: `python manage.py ingest_knowledge_base`.

## Answering flow (the `/chatbot/ask/` endpoint)

```
question
   │
   ▼
embed question (embeddings.py)
   │
   ▼
similarity search in KnowledgeChunk (retriever.py, top_k=5)
   │
   ▼
similarity above threshold?
   │            │
  yes           no
   │            │
   ▼            ▼
build prompt   return fallback:
with context   "I don't know based on
   │           the available Muscle Max
   ▼           information." (grounded=false)
call LLM (generator.py)
   │
   ▼
return {answer, sources, grounded=true}
```

## The grounding rule — non-negotiable for this project

The system prompt sent to the LLM in `generator.py` must instruct it to:
1. Answer using **only** the provided context chunks.
2. Not use outside/general knowledge to fill gaps.
3. Explicitly say it doesn't know when the context doesn't contain the
   answer, rather than guessing.

This is what the project brief calls out as a judging point — a wrong
but confident answer is worse than a correct "I don't know."

## Choosing the embedding + LLM provider

Pick one and record it here once decided (affects `LLM_PROVIDER`,
`LLM_MODEL`, `EMBEDDING_MODEL` in `.env`):
- OpenAI (`text-embedding-3-small` + `gpt-4o-mini`) — simplest to wire up.
- Any HuggingFace `sentence-transformers` model run locally, if avoiding
  API costs matters more than setup time.

## Testing the pipeline manually

```bash
docker compose exec backend python manage.py ingest_knowledge_base
curl -X POST http://localhost:8000/api/chatbot/ask/ \
  -H "Content-Type: application/json" \
  -d '{"question": "How much is the whey protein?"}'
```
