import hashlib
import re
from pathlib import Path
from typing import Any

import chromadb
from chromadb.utils import embedding_functions

CACHE_DIR = Path(__file__).resolve().parent / "vector_db"
CACHE_VERSION = "v2.1"


class SemanticCache:
    def __init__(
        self, db_dir: Path = CACHE_DIR, collection_name: str = "multi_brand_cache"
    ):
        self.client = chromadb.PersistentClient(path=str(db_dir))
        self.emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="paraphrase-multilingual-MiniLM-L12-v2"
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.emb_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def _normalize_query(self, query: str) -> str:
        """Chuẩn hóa câu hỏi để tăng tỷ lệ Match Cache."""
        q = query.lower().strip()
        q = re.sub(r"[^\w\s]", "", q)
        return " ".join(q.split())

    def _is_quality_response(self, response: str) -> bool:
        if not response or len(response.strip()) < 30:
            return False
        has_chinese = any("\u4e00" <= char <= "\u9fff" for char in response)
        words = response.split()
        is_repetitive = len(words) > 20 and (len(set(words)) / len(words)) < 0.35
        return not (has_chinese or is_repetitive)

    def search(self, query: str, similarity_threshold: float = 0.88) -> dict[str, Any]:
        try:
            norm_q = self._normalize_query(query)
            results = self.collection.query(
                query_texts=[norm_q],
                n_results=1,
                where={"version": CACHE_VERSION},
            )
            distances = results.get("distances", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]

            if distances and metadatas:
                similarity = 1.0 - distances[0]
                if similarity >= similarity_threshold and "response" in metadatas[0]:
                    return {
                        "hit": True,
                        "response": metadatas[0]["response"],
                        "similarity": round(similarity, 4),
                    }
        except Exception as error:
            print(f"[Cảnh báo Cache Search]: {error}")

        return {"hit": False, "response": None, "similarity": 0.0}

    def add(self, query: str, response: str) -> None:
        if not self._is_quality_response(response):
            return

        try:
            norm_q = self._normalize_query(query)
            doc_id = hashlib.md5(norm_q.encode("utf-8")).hexdigest()

            self.collection.upsert(
                documents=[norm_q],
                metadatas=[{"response": response, "version": CACHE_VERSION}],
                ids=[doc_id],
            )
        except Exception as error:
            print(f"[Cảnh báo Cache Add]: {error}")
