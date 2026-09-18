"""
Wraps whichever embedding model the team picks (OpenAI, HuggingFace
sentence-transformers, etc.) behind one function so the rest of the
RAG pipeline never touches a vendor SDK directly.
"""


def embed_text(text: str) -> list[float]:
    raise NotImplementedError
