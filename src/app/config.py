import os
import yaml
from pathlib import Path
from typing import Any
from dataclasses import dataclass


@dataclass
class Config:
    data_dir: str
    index_dir: str
    embed_dir: str
    log_dir: str

    chunking_strategy: str
    chunk_size: int
    chunk_overlap: int

    embedding_model: str
    embedding_device: str
    normalize_embeddings: bool

    hnsw_ef_construction: int
    hnsw_ef_search: int
    hnsw_max_neighbors: int

    top_k: int

    post_filter: str
    post_rerank: str
    simularity_threshold: float

    llm_host: str
    llm_model: str
    temperature: float
    max_tokens: int

    log_level: str


def _env_override(var_name: str, default: Any) -> Any:
    v = os.getenv(var_name)
    if not v or v == f"__GMT_VAR_{var_name}__":
        return default
    if isinstance(default, int):
        return int(v)
    if isinstance(default, float):
        return float(v)
    return v


def load_config(path: str | Path = Path(__file__).parent / "config.yaml") -> Config:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    data["data_dir"] = _env_override("DATA_DIR", data["data_dir"])
    data["index_dir"] = _env_override("INDEX_DIR", data["index_dir"])
    data["embed_dir"] = _env_override("EMBED_DIR", data["embed_dir"])
    data["log_dir"] = _env_override("LOG_DIR", data["log_dir"])

    data["chunking_strategy"] = _env_override("CHUNKING_STRATEGY", data["chunking_strategy"])
    data["chunk_size"] = _env_override("CHUNK_SIZE", data["chunk_size"])
    data["chunk_overlap"] = _env_override("CHUNK_OVERLAP", data["chunk_overlap"])

    data["embedding_model"] = _env_override("EMBEDDING_MODEL", data["embedding_model"])
    data["embedding_device"] = _env_override("EMBEDDING_DEVICE", data["embedding_device"])
    data["normalize_embeddings"] = _env_override("NORMALIZE_EMBEDDINGS", data["normalize_embeddings"])

    data["top_k"] = _env_override("TOP_K", data["top_k"])

    data["post_filter"] = _env_override("POST_FILTER", data["post_filter"])
    data["post_rerank"] = _env_override("POST_RERANK", data["post_rerank"])
    data["simularity_threshold"] = _env_override("SIMULARITY_THRESHOLD", data["simularity_threshold"])

    data["llm_host"] = _env_override("LLM_HOST", data["llm_host"])
    data["llm_model"] = _env_override("OLLAMA_MODEL", data["llm_model"])
    data["temperature"] = _env_override("TEMPERATURE", data["temperature"])
    data["max_tokens"] = _env_override("MAX_TOKENS", data["max_tokens"])

    data["log_level"] = _env_override("LOG_LEVEL", data["log_level"])

    return Config(**data)
