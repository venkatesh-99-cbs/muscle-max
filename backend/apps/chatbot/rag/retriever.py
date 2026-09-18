"""
Given a user question, embeds it and queries the vector store for the
top-k most relevant chunks (products, policies, FAQs).
"""


def retrieve(query: str, top_k: int = 5):
    raise NotImplementedError
