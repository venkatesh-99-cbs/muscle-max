"""
Takes the retrieved context + user question, builds the prompt, and
calls the LLM. Must instruct the model to answer ONLY from the given
context and reply with an "I don't know" style response when the
context does not contain the answer.
"""


def generate_answer(question: str, context_chunks: list[str]) -> str:
    raise NotImplementedError
