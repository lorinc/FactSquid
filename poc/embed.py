"""Embedding index for Chain B fact retrieval using sentence-transformers."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from schemas import ExtractedFact

EMBED_MODEL = "all-MiniLM-L6-v2"


class EmbeddingIndex:
    def __init__(
        self,
        facts: list[ExtractedFact],
        embeddings: np.ndarray,
        model_name: str = EMBED_MODEL,
    ) -> None:
        self.facts = facts
        self.embeddings = embeddings  # shape (n, dim), L2-normalised
        self.model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def search(self, query: str, k: int = 10) -> list[tuple[ExtractedFact, float]]:
        model = self._get_model()
        q_emb = model.encode([query], normalize_embeddings=True)[0]
        scores = self.embeddings @ q_emb
        top_idx = np.argsort(scores)[::-1][:k]
        return [(self.facts[i], float(scores[i])) for i in top_idx]

    def save(self, path: Path | str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(str(path.with_suffix(".npy")), self.embeddings)
        path.with_suffix(".facts.json").write_text(
            json.dumps([f.model_dump() for f in self.facts], indent=2)
        )
        print(f"Embeddings saved to {path.with_suffix('.npy')}")

    @classmethod
    def load(cls, path: Path | str, model_name: str = EMBED_MODEL) -> EmbeddingIndex:
        path = Path(path)
        embeddings = np.load(str(path.with_suffix(".npy")))
        facts = [
            ExtractedFact(**d)
            for d in json.loads(path.with_suffix(".facts.json").read_text())
        ]
        return cls(facts=facts, embeddings=embeddings, model_name=model_name)


def build_index(facts: list[ExtractedFact], model_name: str = EMBED_MODEL) -> EmbeddingIndex:
    """Embed all facts and build in-memory cosine-similarity index."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise ImportError(
            "sentence-transformers is required for Chain B.\n"
            "Install with: pip install sentence-transformers"
        )
    model = SentenceTransformer(model_name)
    texts = [f.content for f in facts]
    print(f"Embedding {len(texts)} facts with {model_name}...")
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    return EmbeddingIndex(facts=facts, embeddings=np.array(embeddings), model_name=model_name)
