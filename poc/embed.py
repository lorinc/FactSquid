"""Embedding index for Chain B fact retrieval using OpenAI embeddings API."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from schemas import ExtractedFact

EMBED_MODEL = "text-embedding-3-small"


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

    def search(self, query: str, k: int = 10) -> list[tuple[ExtractedFact, float]]:
        import openai
        client = openai.OpenAI()
        resp = client.embeddings.create(input=[query], model=self.model_name)
        q_emb = np.array(resp.data[0].embedding)
        q_emb /= np.linalg.norm(q_emb)
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
    """Embed all facts via OpenAI API and build in-memory cosine-similarity index."""
    try:
        import openai
    except ImportError:
        raise ImportError(
            "openai is required for Chain B.\n"
            "Install with: pip install openai"
        )
    client = openai.OpenAI()
    texts = [f.content for f in facts]
    print(f"Embedding {len(texts)} facts with {model_name}...")
    resp = client.embeddings.create(input=texts, model=model_name)
    embeddings = np.array([d.embedding for d in resp.data])
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / norms
    return EmbeddingIndex(facts=facts, embeddings=embeddings, model_name=model_name)
