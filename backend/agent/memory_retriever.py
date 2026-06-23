import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_EMBEDDING_MODEL_PATH = Path(
    os.getenv(
        "LOCAL_EMBEDDING_MODEL_PATH",
        r"C:\Users\Likssstt\Documents\Playground\course_rag_system\data\models\bge-small-zh-v1.5",
    )
)


class LocalEmbeddingModel:
    def __init__(self, model_path=DEFAULT_EMBEDDING_MODEL_PATH):
        self.model_path = Path(model_path)
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(str(self.model_path))
        return self._model

    def encode(self, texts):
        vectors = self._load().encode(texts, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]


def cosine_similarity(left, right):
    if not left or not right:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def text_overlap_score(query, content):
    query_text = str(query or "").lower()
    content_text = str(content or "").lower()
    terms = [part for part in query_text.replace("，", " ").replace("？", " ").replace(",", " ").split() if part]
    score = 0.0
    if query_text and query_text in content_text:
        score += 0.35
    score += min(sum(1 for term in terms if term in content_text) * 0.08, 0.24)
    query_chars = {char for char in query_text if "\u4e00" <= char <= "\u9fff"}
    content_chars = {char for char in content_text if "\u4e00" <= char <= "\u9fff"}
    score += min(len(query_chars & content_chars) * 0.015, 0.2)
    return score


def recency_score(created_at):
    try:
        created = datetime.fromisoformat(created_at)
    except Exception:
        return 0.0
    age_days = max((datetime.now(timezone.utc) - created).total_seconds() / 86400, 0)
    return max(0.0, 0.12 - min(age_days / 365, 1) * 0.12)


class MemoryRetriever:
    def __init__(self, core):
        self.core = core

    def retrieve(self, query, top_k=5):
        query_vector = self.core.embedder.encode([query])[0]
        memories = []
        for memory in self.core.list_memories(include_inactive=False):
            memory_vector = self.core.get_memory_vector(memory["memory_id"])
            semantic = cosine_similarity(query_vector, memory_vector)
            importance = float(memory.get("importance", 0.5) or 0.5) * 0.2
            overlap = text_overlap_score(query, memory.get("content", ""))
            recent = recency_score(memory.get("updated_at") or memory.get("created_at", ""))
            score = semantic * 0.58 + importance + overlap + recent
            memories.append(
                {
                    "memory_id": memory["memory_id"],
                    "content": memory["content"],
                    "category": memory["category"],
                    "score": round(score, 4),
                    "source": "memory.json",
                }
            )
        memories.sort(key=lambda item: item["score"], reverse=True)

        profile = self.core.read_user_profile()
        conversation_hits = self.core.search_conversations(query, top_k=3)
        result = {
            "memories": memories[:top_k],
            "profile": profile,
            "conversation_hits": conversation_hits,
        }
        self.core.logger.log(
            "retrieve",
            query=query,
            memory_ids=[memory["memory_id"] for memory in result["memories"]],
            result="success",
            reason="semantic vector retrieval with metadata scoring",
        )
        return result
