import os
import yaml
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    data_dir: str
    index_dir: str
    embed_dir: str
    log_dir: str

    embedding_model: str
    embedding_device: str

    chunk_size: int
    chunk_overlap: int
    top_k: int

    llm_host: str
    llm_model: str
    temperature: float
    max_tokens: int

    log_level: str


def env_override(var_name: str, default: str) -> str:
    v = os.getenv(var_name)
    if not v:
        return default
    # GMT Environment Variablen
    if v == f"__GMT_VAR_{var_name}__":
        return default
    return v


def load_config(path: str | Path = Path(__file__).parent / "config.yaml") -> Config:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    data["data_dir"] = env_override("DATA_DIR", data["data_dir"])
    data["index_dir"] = env_override("INDEX_DIR", data["index_dir"])
    data["embed_dir"] = env_override("EMBED_DIR", data["embed_dir"])
    data["log_dir"] = env_override("LOG_DIR", data["log_dir"])

    data["embedding_model"] = env_override("EMBEDDING_MODEL", data["embedding_model"])
    data["embedding_device"] = env_override("EMBEDDING_DEVICE", data["embedding_device"])

    data["chunk_size"] = env_override("CHUNK_SIZE", data["chunk_size"])
    data["chunk_overlap"] = env_override("CHUNK_OVERLAP", data["chunk_overlap"])
    data["top_k"] = env_override("TOP_K", data["top_k"])

    data["llm_host"] = env_override("LLM_HOST", data["llm_host"])
    data["llm_model"] = env_override("OLLAMA_MODEL", data["llm_model"])
    data["temperature"] = env_override("TEMPERATURE", data["temperature"])
    data["max_tokens"] = env_override("MAX_TOKENS", data["max_tokens"])

    data["log_level"] = env_override("LOG_LEVEL", data["log_level"])

    return Config(**data)
