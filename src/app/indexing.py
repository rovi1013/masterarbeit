import chromadb
import shutil
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any

from app.config import load_config, Config
from app.embedding import get_embed_model
from app.time_marker import mark

logger = logging.getLogger(__name__)

_MARKER_RE = re.compile(r"^(#{1,6})\s+(.*)\s*$")


@dataclass
class RawDocument:
    text: str
    metadata: Dict[str, Any]


# ========== LOAD DOCUMENTS ==========
#
# Aktuell nur .txt im Datensatz; reicht zm testen der Energieeffizien
def _load_documents(data_dir: str) -> List[RawDocument]:
    base = Path(data_dir)
    docs: list[RawDocument] = []

    for path in base.rglob("*"):
        if not path.is_file():
            continue

        suffix = path.suffix.lower()
        if suffix == ".txt":
            doc_type = "txt"
        else:
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if not text.strip():
                logger.warning(f"Leeres Dokument: {path}")
                continue

            metadata = {
                "source": str(path),
                "type": doc_type,
            }
            docs.append(RawDocument(text=text, metadata=metadata))
        except Exception as e:
            logger.error(f"Fehler beim Laden von {path}: {e}")

    logger.info(f"Insgesamt {len(docs)} Dokumente geladen.")
    return docs


# ========== CHUNKING ==========
#
# Verschiedene Chunking Strategien implementieren
# 1. _simple_chunk(): Feste Chunk Größe und fester Overlap, möglichst einfaches aufteilen der Dokumente
# 2. _structure_chunk(): Chunking auf Basis von strukturellen Eigenschaften der Dokumente

def _simple_chunk(doc: RawDocument, chunk_size: int, overlap: int) -> List[RawDocument]:
    """
    Einfache Chunking Strategie mit fester chunk size und einem festen overlap zwischen den Chunks.
    :param doc: Liste der Raw Textdokumente
    :param chunk_size: Größe der Chunks
    :param overlap: Overlap zwischen Chunks
    :return: Liste der gechunkten Dokumente
    """
    text = doc.text
    chunks: list[RawDocument] = []

    start = 0
    step = max(1, chunk_size - overlap)
    chunk_index = 0

    while start < len(text):
        end = start + chunk_size
        chunk_text = text[start:end]
        metadata = dict(doc.metadata)
        metadata["chunk_index"] = chunk_index
        metadata["chunk_start"] = start
        metadata["chunk_end"] = min(end, len(text))
        if chunk_text.strip():
            chunks.append(RawDocument(text=chunk_text, metadata=metadata))
        chunk_index += 1
        start += step

    return chunks


def _structure_chunk(doc: RawDocument, chunk_size: int, chunk_overlap: int) -> List[RawDocument]:
    """
    Chunking auf Basis der Markdown Strukturen der arXiv Dokumente im Datensatz. Mit sections: #-#####;
    besondere Blöcke: ###### (Abstract, Theorem, Definition, Proof, ...). Das Chunking findet auf Basis dieser Blöcke
    statt. Die Information dieser Blöcke (Typ, Titel, ...) wird zusätzlich zu Start und Ende des Chunks als Metadaten
    zum Chunk gespeichert.
    :param doc: Liste der Raw Textdokumente
    :param chunk_size: maximale Größe der Chunks
    :param chunk_overlap: Overlap zwischen Chunks
    :return: Liste der gechunkten Dokumente
    """
    text = doc.text.replace("\r\n", "\n")
    chunks: List[RawDocument] = []
    chunk_index = 0

    # Extract Doc Title: "#..."; fallback wenn kein "#": 1st (non-empty) line in Doc
    doc_title = ""
    for line in text.split("\n"):
        if not line.strip():
            continue
        m = _MARKER_RE.match(line.strip())
        if m and len(m.group(1)) == 1:
            doc_title = m.group(2).strip() or ""
        else:
            doc_title = line.strip()

    block_start = 0
    block_title = ""
    block_type = "text"

    def emit_chunk(chunk_text: str, start_abs: int, end_abs: int):
        nonlocal chunk_index
        meta = dict(doc.metadata)
        meta["doc_title"] = doc_title
        meta["block_title"] = block_title
        meta["block_type"] = block_type
        meta["chunk_index"] = chunk_index
        meta["chunk_start"] = start_abs
        meta["chunk_end"] = end_abs

        chunks.append(RawDocument(text=chunk_text, metadata=meta))
        chunk_index += 1

    # Aufteilen der Dokumente in Blöcke nach "#" und dann Chunks
    def finalize_block(block_end: int):
        if block_end <= block_start:
            return

        block_text = text[block_start:block_end]
        if not block_text.strip():
            return

        start = 0
        while start < len(block_text):
            end = min(start + chunk_size, len(block_text))
            chunk_text = block_text[start:end].strip()

            if chunk_text:
                emit_chunk(chunk_text, block_start + start, block_start + end)

            if end == len(block_text):
                break

            start = end - chunk_overlap if chunk_overlap > 0 else end

    pos = 0
    for line in text.splitlines(keepends=True):
        line_start = pos
        line_end = pos + len(line)
        pos = line_end

        marker = _MARKER_RE.match(line.rstrip("\n"))
        if not marker:
            continue

        finalize_block(line_start)

        hashes = marker.group(1)
        title = (marker.group(2).strip() or "")

        block_title = title
        if len(hashes) == 6:
            block_type = title.split()[0].lower() if title else "special"
        else:
            block_type = "heading"

        block_start = line_end

    finalize_block(len(text))
    return chunks


# ========== INDEXING ==========
def reset_index_dir(index_dir: str) -> None:
    p = Path(index_dir)
    if p.exists():
        logger.info(f"Index-Order {p} wird zurückgesetzt ...")
        shutil.rmtree(p)

    p.mkdir(parents=True, exist_ok=True)
    logger.info(f"Index-Ordner neu angelegt: {p}.")


def _build_index(cfg: Config | None = None, reset_db: bool = False) -> None:
    if cfg is None:
        cfg = load_config()

    if reset_db:
        reset_index_dir(cfg.index_dir)

    # ========== 1. Dokumente Laden ==========
    logger.info(f"Lade Dokumente aus {cfg.data_dir} ...")
    docs = _load_documents(cfg.data_dir)

    # ========== 2. Dokumente Chunken ==========
    logger.info("Chunking der Dokumente ...")
    chunked_docs: list[RawDocument] = []

    mark("CHUNKING_START")
    for doc in docs:
        chunked_docs.extend(_structure_chunk(doc, chunk_size=cfg.chunk_size, chunk_overlap=cfg.chunk_overlap))
    mark("CHUNKING_END")

    logger.info(f"Insgesamt {len(chunked_docs)} Chunks erstellt.")

    if not chunked_docs:
        logger.warning("Keine Chunks gefunden. Abbruch.")
        return

    # ========== 3. Embedding der Dokumente ==========
    logger.info(f"Lade Embedding-Modell {cfg.embedding_model} ...")
    model = get_embed_model(cfg)

    texts = [d.text for d in chunked_docs]
    logger.info("Berechne Embeddings ...")
    mark("EMBEDDING_START")
    embeddings = model.encode(
        texts,
        batch_size=128,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True
    )
    mark("EMBEDDING_END")

    # ========== 4. Datenbank erstellen ==========
    logger.info(f"Erzeuge Chroma DB in {cfg.index_dir} ...")
    client = chromadb.PersistentClient(path=cfg.index_dir)

    # Siehe https://cookbook.chromadb.dev/core/collections/ .
    # Und https://cookbook.chromadb.dev/core/configuration/ für Details zu metadata
    collection = client.get_or_create_collection(
        "rag",
        metadata={
            "hnsw:space": "cosine",
            "hnsw:num_threads": 5,
            "hnsw:batch_size": 10_000,
            "hnsw:sync_threshold": 200_000,
        }
    )

    ids = [str(i) for i in range(len(chunked_docs))]
    metadatas = [d.metadata for d in chunked_docs]

    # BATCH-WISE schreiben in Chroma DB (siehe https://cookbook.chromadb.dev/strategies/batching/).
    # Wichtig, da chromaDB (in der Regel) maximal eine batch size von 5461 akzeptiert.
    # Wird über client.get_max_batch_size() exakt abgerufen, zur Sicherheit mit "-1".
    logger.info("Speichere Embeddings ...")
    batch_size = client.get_max_batch_size() - 1
    total = len(chunked_docs)
    mark("PERSIST_IN_DB_START")

    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch_ids = ids[start:end]
        batch_embs = embeddings[start:end]
        batch_metas = metadatas[start:end]

        logger.debug(f"Füge Batch {start}–{end} von {total} hinzu ...")
        collection.add(
            ids=batch_ids,
            embeddings=batch_embs,
            metadatas=batch_metas,
        )

    mark("PERSIST_IN_DB_END")

    logger.info("========== INDEXING FERTIG ==========")
    return


if __name__ == "__main__":
    from app.simple_logging import setup_logging

    # ENV-Variable 'ANONYMIZED_TELEMETRY' zu 'false' setzen
    setup_logging()
    _build_index()
