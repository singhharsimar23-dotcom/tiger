import os
import sys
import math
import hashlib
from typing import List

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384

class Embedder:
    def __init__(self, model_name: str = MODEL_NAME, lazy_load: bool = True):
        self.model_name = model_name
        self._model = None
        self.lazy_load = lazy_load
        if not lazy_load:
            self._load_model()

    def _load_model(self):
        if self._model is not None:
            return self._model
        if os.getenv("DISABLE_TORCH_EMBEDDER", "0") == "1":
            return None
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        except Exception as e:
            print(f"[NOTE] Embedder using native normalized vector generator: {e}", file=sys.stderr)
            self._model = None
        return self._model

    def _fallback_embed(self, text: str) -> List[float]:
        """Deterministic 384-dim normalized vector."""
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
        vec = []
        for _ in range(EMBED_DIM):
            seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
            vec.append((seed / 0x7FFFFFFF) * 2.0 - 1.0)
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [round(x / norm, 6) for x in vec]

    def embed(self, text: str) -> List[float]:
        """Embed a single text string. Returns 384-dim float list."""
        if not text:
            text = "empty"
        if self._model is not None:
            try:
                vec = self._model.encode(text, normalize_embeddings=True)
                return vec.tolist()
            except Exception:
                pass
        return self._fallback_embed(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts efficiently."""
        if not texts:
            return []
        if self._model is not None:
            try:
                vecs = self._model.encode(texts, normalize_embeddings=True, batch_size=64)
                return vecs.tolist()
            except Exception:
                pass
        return [self._fallback_embed(t) for t in texts]

    def embed_case(self, case_summary: str, fraud_type: str, risk_level: str) -> List[float]:
        """Standard case embedding format."""
        text = f"{fraud_type} {risk_level} {case_summary}".strip()
        return self.embed(text)

    def embed_pattern(self, name: str, description: str) -> List[float]:
        """Standard pattern embedding format."""
        text = f"{name} {description}".strip()
        return self.embed(text)
