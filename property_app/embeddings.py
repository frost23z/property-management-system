"""Text embeddings for semantic search, powered by FastEmbed (ONNX Runtime, no PyTorch)."""

from functools import lru_cache

from django.conf import settings


@lru_cache(maxsize=1)
def get_model():
    """Load the embedding model once per process (the first call downloads the weights)."""
    from fastembed import TextEmbedding  # imported lazily so Django starts fast

    return TextEmbedding(model_name=settings.EMBEDDING_MODEL)


def embed_texts(texts):
    """Embed many strings in one batch. Returns a list of plain float lists."""
    texts = [text for text in texts]
    if not texts:
        return []
    return [vector.tolist() for vector in get_model().embed(texts)]


def embed_text(text):
    """Embed a single string."""
    return embed_texts([text])[0]
