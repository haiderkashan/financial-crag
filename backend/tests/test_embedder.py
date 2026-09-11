"""Tests for DocumentEmbedder and BGE asymmetric embedding generation."""
import math
import uuid
import pytest

from backend.app.ingestion.embedder import DocumentEmbedder, embedder, BGE_QUERY_PREFIX
from backend.app.models.chunk import ChunkCreate


def test_singleton_instance():
    """Verify DocumentEmbedder is a singleton."""
    embedder_a = DocumentEmbedder()
    embedder_b = DocumentEmbedder()
    assert embedder_a is embedder_b
    assert embedder_a is embedder


def test_embed_query_dimension_and_normalization():
    """Verify embed_query returns 384-dimensional normalized float vectors."""
    query = "What were Apple's total net sales and operating expenses?"
    vector = embedder.embed_query(query)

    assert isinstance(vector, list)
    assert len(vector) == 384
    assert all(isinstance(x, float) for x in vector)

    # Cosine normalization: L2 norm should be approximately 1.0
    l2_norm = math.sqrt(sum(x * x for x in vector))
    assert pytest.approx(l2_norm, abs=1e-3) == 1.0


def test_embed_chunks_populates_embedding():
    """Verify embed_chunks batch-encodes chunks without prefix and populates embedding."""
    filing_id = uuid.uuid4()
    chunks = [
        ChunkCreate(
            filing_id=filing_id,
            chunk_index=0,
            section_title="Consolidated Statements of Operations",
            content="Total net sales for fiscal 2023 were $383,285 million.",
            metadata={"source": "test"},
        ),
        ChunkCreate(
            filing_id=filing_id,
            chunk_index=1,
            section_title="Operating Expenses",
            content="Total operating expenses were $54,847 million in 2023.",
            metadata={"source": "test"},
        ),
    ]

    assert len(chunks[0].embedding) == 0
    assert len(chunks[1].embedding) == 0

    embedded = embedder.embed_chunks(chunks)

    assert len(embedded) == 2
    assert len(embedded[0].embedding) == 384
    assert len(embedded[1].embedding) == 384

    l2_norm_0 = math.sqrt(sum(x * x for x in embedded[0].embedding))
    l2_norm_1 = math.sqrt(sum(x * x for x in embedded[1].embedding))
    assert pytest.approx(l2_norm_0, abs=1e-3) == 1.0
    assert pytest.approx(l2_norm_1, abs=1e-3) == 1.0


def test_embed_texts():
    """Verify embed_texts utility function."""
    texts = ["First passage", "Second passage"]
    vectors = embedder.embed_texts(texts)

    assert len(vectors) == 2
    assert len(vectors[0]) == 384
    assert len(vectors[1]) == 384
