"""
Chatbot service layer.
Currently provides a temporary mock service for backend API development.
"""

from typing import Any, Dict


# TODO:
# Replace the mock service with the team lead's RAG pipeline:
# 1. Retrieve relevant knowledge chunks:
#    context_chunks = retriever.retrieve(question, top_k=5)
# 2. Generate an answer using Ollama / LLM:
#    answer = generator.generate_answer(question, context_chunks)
# 3. Return answer, sources, and grounded status.


def generate_mock_answer(question: str) -> Dict[str, Any]:
    """
    Temporary mock service simulating RAG chatbot response.
    Marked as mock/demo behavior to be replaced by the team lead's RAG integration.
    Do not call Ollama or vector stubs directly from this function.
    """
    # Clean question text
    cleaned_question = question.strip() if question else ""

    return {
        "answer": "The AI chatbot integration is currently being prepared.",
        "sources": [],
        "grounded": False,
    }

