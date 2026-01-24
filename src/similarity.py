"""Semantic similarity and embedding utilities for passages (Stage 2)."""
from __future__ import annotations

import logging
import json
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from .passage_store import Passage, PassageStore
from .config import Config

logger = logging.getLogger(__name__)

try:
    import numpy as np
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - environment without Stage 2 deps
    np = None
    SentenceTransformer = None


class SimilarityEngine:
    """Handles embeddings and semantic similarity for passages."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._model: Optional[SentenceTransformer] = None
        self.enabled: bool = False
        self._init_model()

    def _init_model(self) -> None:
        """Initialize embedding model if dependencies are available."""
        if np is None or SentenceTransformer is None:
            logger.warning(
                "sentence-transformers / numpy not available - "
                "Stage 2 semantic features will be disabled."
            )
            self.enabled = False
            return

        try:
            # For MVP we only support local MiniLM model
            model_name = "all-MiniLM-L6-v2"
            logger.info("Loading embedding model %s ...", model_name)
            self._model = SentenceTransformer(model_name)
            self.enabled = True
            logger.info("Embedding model loaded.")
        except Exception as e:  # pragma: no cover - model load issues
            logger.error("Failed to load embedding model: %s", e)
            self._model = None
            self.enabled = False

    # -------- Embedding helpers --------

    def embed_text(self, text: str) -> Optional[List[float]]:
        """Compute embedding for a single passage text."""
        if not self.enabled or not self._model:
            return None
        try:
            vec = self._model.encode([text], show_progress_bar=False)[0]
            return vec.tolist()
        except Exception as e:  # pragma: no cover
            logger.error("Error computing embedding: %s", e)
            return None

    # -------- Similarity search --------

    def _ensure_base_embedding(self, store: PassageStore, passage: Passage) -> Optional[List[float]]:
        """Ensure a passage has an embedding, computing and storing if needed."""
        if passage.embedding:
            try:
                return json.loads(passage.embedding)
            except Exception:
                logger.warning("Invalid embedding JSON for passage %s", passage.id)

        vec = self.embed_text(passage.text)
        if vec is not None:
            store.set_passage_embedding(passage.id, vec)
        return vec

    def find_related_passages(
        self, store: PassageStore, base_passage: Passage, top_k: int = 2
    ) -> List[Passage]:
        """Find semantically related passages from different documents.

        Falls back to random selection if embeddings are disabled or unavailable.
        """
        # Fallback when semantic features are disabled
        if not self.enabled or not self._model or np is None:
            logger.info("SimilarityEngine disabled - using random related passages.")
            return self._random_related_passages(store, base_passage, top_k)

        base_vec = self._ensure_base_embedding(store, base_passage)
        if base_vec is None:
            logger.info("Could not compute base embedding - using random fallback.")
            return self._random_related_passages(store, base_passage, top_k)

        session: Session = store.get_session()
        try:
            # Candidates: other passages with embeddings, different source file
            candidates: List[Passage] = (
                session.query(Passage)
                .filter(
                    Passage.id != base_passage.id,
                    Passage.source_file != base_passage.source_file,
                    Passage.embedding.isnot(None),
                )
                .all()
            )

            if not candidates:
                logger.info("No candidate passages with embeddings - random fallback.")
                return self._random_related_passages(store, base_passage, top_k)

            base_vec_np = np.asarray(base_vec, dtype="float32")
            scores: List[tuple[Passage, float]] = []

            for p in candidates:
                try:
                    emb = json.loads(p.embedding)
                    emb_np = np.asarray(emb, dtype="float32")
                    # Cosine similarity
                    denom = (np.linalg.norm(base_vec_np) * np.linalg.norm(emb_np))
                    if denom == 0:
                        continue
                    sim = float(np.dot(base_vec_np, emb_np) / denom)
                    scores.append((p, sim))
                except Exception:
                    continue

            scores.sort(key=lambda x: x[1], reverse=True)
            return [p for p, _ in scores[:top_k]]
        finally:
            session.close()

    def _random_related_passages(
        self, store: PassageStore, base_passage: Passage, top_k: int
    ) -> List[Passage]:
        """Random fallback for related passages (different documents)."""
        session: Session = store.get_session()
        try:
            query = (
                session.query(Passage)
                .filter(
                    Passage.id != base_passage.id,
                    Passage.source_file != base_passage.source_file,
                )
                .order_by(func.random())
                .limit(top_k)
            )
            return list(query.all())
        finally:
            session.close()

