from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any
from pypdf import PdfReader
import chromadb
import shutil
import logging

from app.config import load_config, Config
from app.embedding import get_embed_model
from app.time_marker import mark

logger = logging.getLogger(__name__)


@dataclass
class RawDocument:
    text: str
    metadata: Dict[str, Any]


# ========== LOAD DOCUMENTS ==========
#
# Aktuell nur .txt im Datensatz; reicht zm testen der Energieeffizienz

def load_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def load_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    texts: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        texts.append(page_text)
    return "\n".join(texts)


def load_documents(data_dir: str) -> List[RawDocument]:
    base = Path(data_dir)
    docs: list[RawDocument] = []

    for path in base.rglob("*"):
        if not path.is_file():
            continue

        suffix = path.suffix.lower()

        if suffix == ".txt":
            loader = load_txt
            doc_type = "txt"
        elif suffix == ".pdf":
            loader = load_pdf
            doc_type = "pdf"
        else:
            # andere Dateitypen aktuell ignorieren
            continue

        try:
            text = loader(path)
            if not text.strip():
                logger.debug(f"Leeres Dokument: {path}")
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
# 1. simple_chunk(): Feste Chunk Größe und fester Overlap, möglichst einfaches aufteilen der Dokumente
# 2. ....

def simple_chunk(doc: RawDocument, chunk_size: int, overlap: int) -> List[RawDocument]:
    """
    Einfache Chunking Strategie mit fester chunk size und einem festen overlap zwischen den Chunks.
    :param doc: Liste der Klasse RawDocument
    :param chunk_size: Größe der Chunks
    :param overlap: Overlap zwischen Chunks
    :return: Liste der gechunkten Dokumente
    """
    text = doc.text
    chunks: list[RawDocument] = []

    start = 0
    n = len(text)
    step = max(1, chunk_size - overlap)
    chunk_index = 0

    while start < n:
        end = start + chunk_size
        chunk_text = text[start:end]
        if chunk_text.strip():
            metadata = dict(doc.metadata)
            metadata["chunk_index"] = chunk_index
            chunks.append(RawDocument(text=chunk_text, metadata=metadata))
            chunk_index += 1
        start += step

    return chunks


# ========== INDEXING ==========


def reset_index_dir(index_dir: str) -> None:
    p = Path(index_dir)
    if p.exists():
        logger.info(f"Index-Order {p} wird zurückgesetzt ...")
        shutil.rmtree(p)

    p.mkdir(parents=True, exist_ok=True)
    logger.info(f"Index-Ordner neu angelegt: {p}.")


def build_index(cfg: Config | None = None, reset_db: bool = False) -> None:
    if cfg is None:
        cfg = load_config()

    if reset_db:
        reset_index_dir(cfg.index_dir)

    # ========== 1. Dokumente Laden ==========
    logger.info(f"Lade Dokumente aus {cfg.data_dir} ...")
    docs = load_documents(cfg.data_dir)

    # ========== 2. Dokumente Chunken ==========
    logger.info("Chunking der Dokumente ...")
    chunked_docs: list[RawDocument] = []
    for doc in docs:
        chunked_docs.extend(simple_chunk(doc, cfg.chunk_size, cfg.chunk_overlap))

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
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=True)
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
            "hnsw:num_threads": 4,
            "hnsw:batch_size": 10_000,
            "hnsw:sync_threshold": 200_000,
        },
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

        logger.info(f"Füge Batch {start}–{end} von {total} hinzu ...")
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
    build_index()
