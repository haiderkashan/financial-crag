"""Document embedding engine utilizing local sentence-transformers (BAAI/bge-small-en-v1.5)."""
import logging
from typing import Optional

from backend.app.core.config import settings
from backend.app.models.chunk import ChunkCreate

logger = logging.getLogger(__name__)

BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class DocumentEmbedder:
    """Singleton embedding engine generating dense vector representations for chunks and queries."""

    _instance: Optional["DocumentEmbedder"] = None

    def __new__(cls) -> "DocumentEmbedder":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._model = None
        return cls._instance

    @property
    def model(self):
        """Lazy-load the SentenceTransformer model on first invocation."""
        if self._model is None:
            logger.info(
                "Loading embedding model '%s' on device '%s'...",
                settings.EMBEDDING_MODEL_NAME,
                settings.EMBEDDING_DEVICE,
            )
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                settings.EMBEDDING_MODEL_NAME,
                device=settings.EMBEDDING_DEVICE,
            )
            logger.info("Embedding model loaded successfully.")
        return self._model

    def embed_chunks(
        self, chunks: list[ChunkCreate], batch_size: Optional[int] = None
    ) -> list[ChunkCreate]:
        """Batch encode document chunks with raw content (no query prefix).

        CRITICAL FOR BGE:
        Do NOT prefix document chunks. Chunks are ingested as raw document passages.
        L2 normalization is enforced via normalize_embeddings=True.
        """
        if not chunks:
            return []

        bs = batch_size or settings.EMBEDDING_BATCH_SIZE
        texts = [chunk.content for chunk in chunks]

        logger.info("Generating embeddings for %d chunks (batch_size=%d)...", len(chunks), bs)
        embeddings = self.model.encode(
            texts,
            batch_size=bs,
            show_progress_bar=False,
            normalize_embeddings=True,
        )

        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = [float(x) for x in embedding]

        return chunks

    def embed_texts(
        self, texts: list[str], batch_size: Optional[int] = None
    ) -> list[list[float]]:
        """Batch encode raw strings without query prefix."""
        if not texts:
            return []

        bs = batch_size or settings.EMBEDDING_BATCH_SIZE
        embeddings = self.model.encode(
            texts,
            batch_size=bs,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return [[float(x) for x in vec] for vec in embeddings]

    def embed_query(self, query: str) -> list[float]:
        """Encode a search query with BGE asymmetric instruction prefix.

        CRITICAL FOR BGE:
        Queries must be prefixed with:
        'Represent this sentence for searching relevant passages: '
        """
        prefixed_query = f"{BGE_QUERY_PREFIX}{query.strip()}"
        embedding = self.model.encode(
            prefixed_query,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return [float(x) for x in embedding]


embedder = DocumentEmbedder()
