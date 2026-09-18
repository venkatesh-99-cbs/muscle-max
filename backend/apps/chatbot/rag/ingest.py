"""
Loads business data (products, policies, FAQs) from the database / docs,
splits it into chunks, generates embeddings, and stores them in the
vector store (pgvector table). Run via:
    python manage.py shell -c "from apps.chatbot.rag.ingest import run; run()"
or the management command: python manage.py ingest_knowledge_base
"""


def run():
    raise NotImplementedError
