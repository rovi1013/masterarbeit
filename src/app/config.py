import os
import yaml
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    data_dir: str
    index_dir: str

    embedding_model: str
    embedding_device: str
    enable_context: bool

    chunk_size: int
    chunk_overlap: int
    top_k: int

    llm_host: str
    llm_model: str
    temperature: float
    max_tokens: int

    log_level: str


def load_config(path: str | Path = Path(__file__).parent / "config.yaml") -> Config:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Default: get llm_model from config.yaml; Docker: get llm_model from .env
    # llm_model muss in Docker über das environment zur Erstellungszeit des ollama containers bekannt sein,
    # weil geprüft wird, ob das Modell bereits gecached ist oder noch heruntergeladen werden muss. Dafür
    # muss der container wissen, welches llm_model verwendet werden soll.
    data["llm_model"] = os.getenv("OLLAMA_MODEL", data["llm_model"])
    # RAG-APP mit relativen Pfaden (../data/___); Docker mit statischen (/src/data/___)
    data["data_dir"] = os.getenv("DATA_DIR", data["data_dir"])
    data["index_dir"] = os.getenv("INDEX_DIR", data["index_dir"])

    return Config(**data)
