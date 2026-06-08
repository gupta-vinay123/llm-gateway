import numpy as np
import json
import hashlib
from sentence_transformers import SentenceTransformer
from redis import Redis
from app.core.config import settings

class SemanticCache:
    def __init__(self):
        self.redis = Redis.from_url(settings.redis_url, decode_responses=True)
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.threshold = settings.similarity_threshold
        self.ttl = settings.cache_ttl
        self._ensure_index()
    
    def get_exact(self, query: str) -> dict | None:
        key = f"exact:{hashlib.md5(query.encode()).hexdigest()}"
        response = self.redis.get(key)
        if response:
            return {
                "response": response,
                "cached_query": query,
                "similarity": 1.0,
                "cache_hit": True,
                "cache_type": "exact"
            }
        return None

    def set_exact(self, query: str, response: str) -> None:
        key = f"exact:{hashlib.md5(query.encode()).hexdigest()}"
        self.redis.set(key, response, ex=self.ttl)

    def _ensure_index(self):
        try:
            self.redis.execute_command("FT.INFO", "cache_index")
            print("Cache index already exists")
        except Exception:
            # Index doesn't exist — create it
            self.redis.execute_command(
                "FT.CREATE", "cache_index",
                "ON", "HASH",
                "PREFIX", "1", "cache:",
                "SCHEMA",
                "embedding", "VECTOR", "FLAT", "6",
                "TYPE", "FLOAT32",
                "DIM", "384",
                "DISTANCE_METRIC", "COSINE",
                "query", "TEXT",
                "response", "TEXT"
            )
            print("Cache index created")

    def _embed(self, text: str) -> np.ndarray:
        return self.model.encode(text, normalize_embeddings=True)

    def _vec_to_bytes(self, vec: np.ndarray) -> bytes:
        return vec.astype(np.float32).tobytes()

    def get(self, query: str) -> dict | None:
        embedding = self._embed(query)
        vec_bytes = self._vec_to_bytes(embedding)

        try:
            results = self.redis.execute_command(
                "FT.SEARCH", "cache_index",
                f"*=>[KNN 1 @embedding $vec AS score]",
                "PARAMS", "2", "vec", vec_bytes,
                "SORTBY", "score",
                "RETURN", "3", "query", "response", "score",
                "DIALECT", "2"
            )

            if results[0] == 0:
                return None

            # results format: [count, key, [field, value, ...]]
            fields = results[2]
            field_dict = dict(zip(fields[::2], fields[1::2]))

            score = float(field_dict.get("score", 1.0))
            # cosine distance → similarity
            similarity = 1 - score

            if similarity >= self.threshold:
                return {
                    "response": field_dict.get("response"),
                    "cached_query": field_dict.get("query"),
                    "similarity": round(similarity, 4),
                    "cache_hit": True,
                    "cache_type": "semantic"
                }
        except Exception as e:
            print(f"Cache lookup error: {e}")

        return None

    def set(self, query: str, response: str) -> None:
        embedding = self._embed(query)
        vec_bytes = self._vec_to_bytes(embedding)
        key = f"cache:{hashlib.md5(query.encode()).hexdigest()}"

        self.redis.hset(key, mapping={
            "query": query,
            "response": response,
            "embedding": vec_bytes
        })
        self.redis.expire(key, self.ttl)
        self.set_exact(query, response)
        
    def invalidate(self, query: str) -> bool:
        key = f"cache:{hashlib.md5(query.encode()).hexdigest()}"
        return bool(self.redis.delete(key))

    def flush(self) -> None:
        keys = self.redis.keys("cache:*")
        if keys:
            self.redis.delete(*keys)

# singleton
semantic_cache = SemanticCache()