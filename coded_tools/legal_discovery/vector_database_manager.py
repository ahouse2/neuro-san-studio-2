import asyncio
import hashlib
import logging
import random
import time

from config.config import (
    QDRANT_HOST,
    QDRANT_PORT,
)

try:  # pragma: no cover - optional
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import (
        Distance,
        FieldCondition,
        Filter,
        MatchValue,
        PointIdsList,
        PointStruct,
        VectorParams,
    )
except Exception:  # pragma: no cover - qdrant not available
    QdrantClient = None
    Distance = FieldCondition = Filter = MatchValue = PointIdsList = PointStruct = VectorParams = None


from neuro_san.interfaces.coded_tool import CodedTool


class _HashEmbedder:
    """Deterministic fallback embedder using SHA256 hashes."""

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def _embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        # Repeat digest to fill dimension and normalise to [0,1]
        data = (digest * ((self.dim // len(digest)) + 1))[: self.dim]
        return [b / 255 for b in data]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover - simple
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:  # pragma: no cover - simple
        return self._embed(text)


class _InMemoryCollection:
    """Minimal stand‑in for a vector collection."""

    def __init__(self) -> None:
        self._docs: dict[str, dict] = {}

    def add(
        self,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
        embeddings: list[list[float]] | None = None,
    ) -> None:
        for doc, md, _id in zip(documents, metadatas, ids):
            self._docs[_id] = {"document": doc, "metadata": md}

    def query(
        self,
        query_texts: list[str] | None = None,
        query_embeddings: list[list[float]] | None = None,
        n_results: int = 10,
        where: dict | None = None,
    ) -> dict:
        docs = []
        metas = []
        ids = []
        for _id, data in self._docs.items():
            md = data["metadata"]
            if where and md.get("visibility") != where.get("visibility"):
                continue
            docs.append(data["document"])
            metas.append(md | {"id": _id})
            ids.append(_id)
            if len(docs) >= n_results:
                break
        return {"documents": [docs], "metadatas": [metas], "ids": [ids]}

    def get(self, ids: list[str]) -> dict:  # pragma: no cover - trivial
        found = [_id for _id in ids if _id in self._docs]
        return {"ids": found}

    def delete(self, ids: list[str]) -> None:  # pragma: no cover - trivial
        for _id in ids:
            self._docs.pop(_id, None)

    def count(self) -> int:  # pragma: no cover - trivial
        return len(self._docs)

    def persist(self) -> None:  # pragma: no cover - no-op
        return None


class _InMemoryClient:
    def get_or_create_collection(self, _name: str) -> _InMemoryCollection:  # pragma: no cover - simple
        return _InMemoryCollection()


_GLOBAL_CLIENT = None


class VectorDatabaseManager(CodedTool):
    """Vector DB manager preferring Qdrant with graceful fallbacks."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.embedder = self._init_embedder()
        self.dim = len(self.embedder.embed_documents(["dimension"])[0])
        self.use_qdrant = False

        if QdrantClient is not None:
            try:
                self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
                for name in ["legal_documents", "chat_messages", "conversations"]:
                    try:
                        self.client.get_collection(name)
                    except Exception:
                        self.client.create_collection(
                            name,
                            vectors_config=VectorParams(size=self.dim, distance=Distance.COSINE),
                        )
                self.use_qdrant = True
            except Exception as exc:  # pragma: no cover - best effort
                logging.warning("Qdrant unavailable (%s); falling back", exc)

        if not self.use_qdrant:
            self._init_fallback()

        # For compatibility with previous code paths
        if self.use_qdrant:
            self.collection = "legal_documents"
            self.msg_collection = "chat_messages"
            self.convo_collection = "conversations"

        self._query_cache: dict[tuple, dict] = {}
        self._msg_cache: dict[tuple, dict] = {}
        self._convo_cache: dict[tuple, dict] = {}

    # ---- initialisation helpers -------------------------------------------

    def _init_embedder(self):  # pragma: no cover - simple
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer("all-MiniLM-L6-v2")

            class _STEmbedder:
                def __init__(self, m):
                    self.m = m

                def embed_documents(self, texts: list[str]) -> list[list[float]]:
                    return self.m.encode(texts, normalize_embeddings=True).tolist()

                def embed_query(self, text: str) -> list[float]:
                    return self.m.encode([text], normalize_embeddings=True)[0].tolist()

            return _STEmbedder(model)
        except Exception:  # pragma: no cover - fallback
            return _HashEmbedder()

    def _init_fallback(self) -> None:
        global _GLOBAL_CLIENT
        if _GLOBAL_CLIENT is None:
            _GLOBAL_CLIENT = _InMemoryClient()
        self.client = _GLOBAL_CLIENT
        self.collection = self.client.get_or_create_collection("legal_documents")
        self.msg_collection = self.client.get_or_create_collection("chat_messages")
        self.convo_collection = self.client.get_or_create_collection("conversations")

    # ---- utility ----------------------------------------------------------

    def _invalidate_cache(self) -> None:
        self._query_cache.clear()
        self._msg_cache.clear()
        self._convo_cache.clear()

    def _build_filter(self, where: dict | None):
        if not where or not self.use_qdrant:
            return None
        conditions = [
            FieldCondition(key=k, match=MatchValue(value=v)) for k, v in where.items()
        ]
        return Filter(must=conditions)

    def _with_retry(self, func, *args, max_retries: int = 4, base_delay: float = 0.25, **kwargs):
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as exc:  # pragma: no cover - best effort
                last_exc = exc
                delay = base_delay * (2 ** attempt) + random.uniform(0, base_delay)
                logging.warning("vector op failed (%s); retrying in %.2fs", exc, delay)
                time.sleep(delay)
        if last_exc:
            raise last_exc
        return None

    def persist(self) -> None:  # pragma: no cover - best effort
        try:
            if not self.use_qdrant:
                self.client.persist()
        except Exception as exc:
            logging.warning("Vector DB persist failed: %s", exc)

    # ---- document operations ---------------------------------------------

    def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
        embeddings: list[list[float]] | None = None,
    ) -> None:
        if self.use_qdrant:
            if embeddings is None:
                embeddings = self.embedder.embed_documents(documents)
            points = [
                PointStruct(id=_id, vector=emb, payload=md | {"document": doc})
                for doc, md, _id, emb in zip(documents, metadatas, ids, embeddings)
            ]
            self.client.upsert(collection_name=self.collection, points=points)
        else:
            # existing logic with metadata padding
            safe_docs: list[str] = []
            safe_metadatas: list[dict] = []
            safe_ids: list[str] = []
            safe_embeddings: list[list[float]] = []

            if len(metadatas) < len(documents):
                metadatas = metadatas + [{}] * (len(documents) - len(metadatas))

            emb_iter = embeddings or [None] * len(documents)
            for doc, md, doc_id, emb in zip(documents, metadatas, ids, emb_iter):
                try:
                    existing = self.collection.get(ids=[doc_id])
                    if existing and existing.get("ids"):
                        continue
                except Exception:
                    pass

                safe_docs.append(doc)
                safe_ids.append(doc_id)
                if emb is not None:
                    safe_embeddings.append(emb)
                if not isinstance(md, dict) or not md:
                    safe_metadatas.append({"source": "unknown", "id": doc_id})
                else:
                    cleaned = {k: v for k, v in md.items() if v}
                    safe_metadatas.append(cleaned or {"source": "unknown", "id": doc_id})

            if not safe_docs:
                return

            if embeddings:
                self._with_retry(
                    self.collection.add,
                    documents=safe_docs,
                    metadatas=safe_metadatas,
                    ids=safe_ids,
                    embeddings=safe_embeddings,
                )
            else:
                self._with_retry(
                    self.collection.add,
                    documents=safe_docs,
                    metadatas=safe_metadatas,
                    ids=safe_ids,
                )
        self._invalidate_cache()

    def add_documents_batched(
        self,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
        embeddings: list[list[float]] | None = None,
        batch_size: int = 256,
    ) -> None:
        total = len(documents)
        if len(metadatas) < total:
            metadatas = metadatas + [{}] * (total - len(metadatas))
        if embeddings is not None and len(embeddings) < total:
            embeddings = embeddings + [[]] * (total - len(embeddings))  # type: ignore

        for i in range(0, total, batch_size):
            j = min(i + batch_size, total)
            docs = documents[i:j]
            mds = metadatas[i:j]
            _ids = ids[i:j]
            embs = embeddings[i:j] if embeddings is not None else None
            self.add_documents(docs, mds, _ids, embs)
        try:
            self.persist()
        except Exception:
            pass

    async def aadd_documents(
        self,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
        embeddings: list[list[float]] | None = None,
    ) -> None:
        await asyncio.to_thread(self.add_documents, documents, metadatas, ids, embeddings)

    def query(
        self,
        query_texts: list[str],
        n_results: int = 10,
        where: dict | None = None,
    ) -> dict:
        key = (tuple(query_texts), n_results, frozenset(where.items()) if where else None)
        if key in self._query_cache:
            return self._query_cache[key]

        if self.use_qdrant:
            vector = self.embedder.embed_query(query_texts[0])
            flt = self._build_filter(where)
            hits = self.client.search(
                collection_name=self.collection,
                query_vector=vector,
                limit=n_results,
                query_filter=flt,
                with_payload=True,
            )
            docs = [h.payload.get("document", "") for h in hits]
            metas = [
                {k: v for k, v in (h.payload or {}).items() if k != "document"}
                for h in hits
            ]
            ids = [str(h.id) for h in hits]
            result = {"documents": [docs], "metadatas": [metas], "ids": [ids]}
        else:
            result = self.collection.query(
                query_texts=query_texts, n_results=n_results, where=where
            )

        self._query_cache[key] = result
        return result

    def get_document_count(self) -> int:
        if self.use_qdrant:
            return self.client.count(self.collection).count  # type: ignore[attr-defined]
        return self.collection.count()

    def delete_documents(self, ids: list[str]) -> None:
        if self.use_qdrant:
            self.client.delete(
                collection_name=self.collection,
                points_selector=PointIdsList(points=ids),
            )
        else:
            self.collection.delete(ids=ids)
        self._invalidate_cache()

    # ---- message operations ----------------------------------------------

    def add_messages(
        self,
        messages: list[str],
        metadatas: list[dict],
        ids: list[str],
        embeddings: list[list[float]] | None = None,
    ) -> None:
        if embeddings is None:
            embeddings = self.embedder.embed_documents(messages)
        if self.use_qdrant:
            points = [
                PointStruct(id=_id, vector=emb, payload=md | {"message": msg})
                for msg, md, _id, emb in zip(messages, metadatas, ids, embeddings)
            ]
            self.client.upsert(collection_name=self.msg_collection, points=points)
        else:
            if len(metadatas) < len(messages):
                metadatas = metadatas + [{}] * (len(messages) - len(metadatas))
            safe_md = []
            for md, mid in zip(metadatas, ids):
                if not isinstance(md, dict) or not md:
                    safe_md.append({"message_id": mid, "visibility": "public"})
                else:
                    md.setdefault("visibility", "public")
                    safe_md.append(md)
            self.msg_collection.add(
                documents=messages,
                metadatas=safe_md,
                ids=ids,
                embeddings=embeddings,
            )
        self._invalidate_cache()

    async def aadd_messages(
        self,
        messages: list[str],
        metadatas: list[dict],
        ids: list[str],
        embeddings: list[list[float]] | None = None,
    ) -> None:
        await asyncio.to_thread(self.add_messages, messages, metadatas, ids, embeddings)

    def add_conversations(
        self,
        texts: list[str],
        metadatas: list[dict],
        ids: list[str],
        embeddings: list[list[float]] | None = None,
    ) -> None:
        if embeddings is None:
            embeddings = self.embedder.embed_documents(texts)
        if self.use_qdrant:
            points = [
                PointStruct(id=_id, vector=emb, payload=md | {"conversation": txt})
                for txt, md, _id, emb in zip(texts, metadatas, ids, embeddings)
            ]
            self.client.upsert(collection_name=self.convo_collection, points=points)
        else:
            if len(metadatas) < len(texts):
                metadatas = metadatas + [{}] * (len(texts) - len(metadatas))
            self.convo_collection.add(
                documents=texts,
                metadatas=metadatas,
                ids=ids,
                embeddings=embeddings,
            )
        self._invalidate_cache()

    async def aadd_conversations(
        self,
        texts: list[str],
        metadatas: list[dict],
        ids: list[str],
        embeddings: list[list[float]] | None = None,
    ) -> None:
        await asyncio.to_thread(self.add_conversations, texts, metadatas, ids, embeddings)

    def query_messages(
        self,
        query_texts: list[str] | None = None,
        n_results: int = 10,
        where: dict | None = None,
        query_embeddings: list[list[float]] | None = None,
    ) -> dict:
        key = (
            tuple(query_texts) if query_texts else None,
            n_results,
            frozenset(where.items()) if where else None,
            tuple(map(tuple, query_embeddings)) if query_embeddings else None,
        )
        if key in self._msg_cache:
            return self._msg_cache[key]

        if self.use_qdrant:
            if query_embeddings is None:
                query_embeddings = [self.embedder.embed_query(query_texts[0])]
            flt = self._build_filter(where)
            hits = self.client.search(
                collection_name=self.msg_collection,
                query_vector=query_embeddings[0],
                limit=n_results,
                query_filter=flt,
                with_payload=True,
            )
            docs = [h.payload.get("message", "") for h in hits]
            metas = [
                {k: v for k, v in (h.payload or {}).items() if k != "message"}
                for h in hits
            ]
            ids = [str(h.id) for h in hits]
            result = {"documents": [docs], "metadatas": [metas], "ids": [ids]}
        else:
            result = self.msg_collection.query(
                query_texts=query_texts if query_embeddings is None else None,
                query_embeddings=query_embeddings,
                n_results=n_results,
                where=where,
            )
        self._msg_cache[key] = result
        return result

    def query_conversations(
        self,
        query_texts: list[str],
        n_results: int = 10,
        where: dict | None = None,
    ) -> dict:
        key = (tuple(query_texts), n_results, frozenset(where.items()) if where else None)
        if key in self._convo_cache:
            return self._convo_cache[key]

        if self.use_qdrant:
            vector = self.embedder.embed_query(query_texts[0])
            flt = self._build_filter(where)
            hits = self.client.search(
                collection_name=self.convo_collection,
                query_vector=vector,
                limit=n_results,
                query_filter=flt,
                with_payload=True,
            )
            docs = [h.payload.get("conversation", "") for h in hits]
            metas = [
                {k: v for k, v in (h.payload or {}).items() if k != "conversation"}
                for h in hits
            ]
            ids = [str(h.id) for h in hits]
            result = {"documents": [docs], "metadatas": [metas], "ids": [ids]}
        else:
            result = self.convo_collection.query(
                query_texts=query_texts, n_results=n_results, where=where
            )
        self._convo_cache[key] = result
        return result

    # ---- async wrappers ---------------------------------------------------

    async def aquery(
        self, query_texts: list[str], n_results: int = 10, where: dict | None = None
    ) -> dict:
        return await asyncio.to_thread(self.query, query_texts, n_results, where)

    async def aquery_messages(
        self,
        query_texts: list[str] | None = None,
        n_results: int = 10,
        where: dict | None = None,
        query_embeddings: list[list[float]] | None = None,
    ) -> dict:
        return await asyncio.to_thread(
            self.query_messages, query_texts, n_results, where, query_embeddings
        )

    async def aquery_conversations(
        self, query_texts: list[str], n_results: int = 10, where: dict | None = None
    ) -> dict:
        return await asyncio.to_thread(self.query_conversations, query_texts, n_results, where)

