import chromadb
import logging
import re

from pathlib import Path
from rank_bm25 import BM25Okapi
from typing import Any

from app.config import Config, load_config
from app.embedding import get_embed_model

logger = logging.getLogger(__name__)
TOK = re.compile(r"\w+", re.UNICODE)


def get_collection(cfg: Config | None = None):
    if cfg is None:
        cfg = load_config()

    client = chromadb.PersistentClient(path=cfg.index_dir)
    return client.get_or_create_collection("rag")


def _apply_metadata_filter(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    drop_types = {"title", "contents", "index", "doi", "pacs", "msc", "acknowledgments"}
    min_span_chars = 50

    out: list[dict[str, Any]] = []
    for h in hits:
        m = h["meta"]

        bt = str(m.get("block_type", "") or "").strip().lower()
        if bt in drop_types:
            continue

        start = int(m.get("chunk_start", 0))
        end = int(m.get("chunk_end", 0))
        if end - start < min_span_chars:
            continue

        out.append(h)

    return out


def _enhance_context(docs: list[str], metas: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for doc, m in zip(docs, metas):
        doc_title = m.get("doc_title", "").strip()
        block_title = m.get("block_title", "").strip()
        block_type = m.get("block_type", "").strip()

        header = (
            "### Metadaten\n"
            f"- Document title: {doc_title}\n"
            f"- Block title: {block_title}\n"
            f"- Block type: {block_type}\n"
            "### Inhalt\n"
        )
        out.append(header + doc)

    return out


def _bm25_rerank(question: str, docs: list[str], metas: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    def tok(s: str) -> list[str]:
        return TOK.findall((s or "").lower())

    tokenized_question = tok(question)
    if not tokenized_question:
        return docs, metas

    tokenized_docs = [tok(d) for d in docs]
    bm25 = BM25Okapi(tokenized_docs)
    scores = bm25.get_scores(tokenized_question)

    # BM25: hoher score = besserer Match
    order = sorted(range(len(docs)), key=lambda i: scores[i], reverse=True)
    logger.debug(f"Neue Reihenfolge der Textsegmente nach BM25 Re-Ranking: {order}.")
    return [docs[i] for i in order], [metas[i] for i in order]


def retrieve(cfg: Config, question: str):
    collection = get_collection(cfg)

    model = get_embed_model(cfg)
    query_emb = model.encode(
        [question],
        batch_size=128,
        convert_to_numpy=True,
        normalize_embeddings=cfg.normalize_embeddings,
    )

    retrieval_result = collection.query(
        query_embeddings=query_emb,
        n_results=cfg.top_k,
        include=["metadatas", "distances"],
    )

    metas = retrieval_result.get("metadatas", [[]])[0]
    dists = retrieval_result.get("distances", [[]])[0]
    hits = [{"meta": meta, "dist": float(dist)} for meta, dist in zip(metas, dists)]

    chunking_is_structure = (cfg.chunking_strategy == "structure")
    # OPTION 1) Metadaten Filter
    if cfg.metadata_filter and chunking_is_structure:
        hits = _apply_metadata_filter(hits)

    # OPTION 2) Filter über Distanz; nur wenn threshold eine gültige Zahl ist
    threshold = float(cfg.simularity_threshold)
    if 0.0 < threshold <= 2.0:
        hits = [h for h in hits if h["dist"] <= threshold]

    # Falls Filter alles herausfiltern
    if not hits:
        return [], []

    # Dokumentsegmente laden, werden für Re-Ranking und Metadata-Enhancement benötigt
    file_cache: dict[str, str] = {}
    docs: list[str] = []
    out_metas: list[dict[str, Any]] = []

    for rank, h in enumerate(hits, start=1):
        meta = h["meta"]
        dist = h["dist"]

        src = meta.get("source")
        start = int(meta.get("chunk_start", 0))
        end = int(meta.get("chunk_end", 0))

        if not src or end <= start:
            continue
        try:
            if src not in file_cache:
                file_cache[src] = Path(src).read_text(encoding="utf-8", errors="ignore")
            doc = file_cache[src][start:end].strip()
            if not doc:
                continue
        except Exception as e:
            logger.warning(f"Chunk konnte nicht geladen werden: {src} ({e})")
            continue

        docs.append(doc)
        out_metas.append(meta)

        logger.debug(
            f"hit#{rank}: "
            f"source={meta.get('source')} "
            f"chunk={meta.get('chunk_index')} "
            f"dist={dist:.4f}"
        )

    # Falls Dokumentsegmente nicht geladen werden können
    if not docs:
        return [], []

    # OPTION 3) BM25 Re-Ranking der Dokumente
    if cfg.post_bm25_rerank:
        docs, out_metas = _bm25_rerank(question, docs, out_metas)

    # OPTION 4) Metadaten als Header der Dokumente hinzufügen
    if cfg.metadata_enhancement and chunking_is_structure:
        docs = _enhance_context(docs, out_metas)

    logger.debug(f"Retriever hat {len(docs)} Dokumente zurückgegeben.")
    return docs, out_metas
