import requests

from app.config import Config


class OllamaClient:
    def __init__(self, cfg: Config):
        self.host = cfg.llm_host.rstrip("/")
        self.model = cfg.llm_model
        self.temperature = cfg.temperature
        self.max_tokens = cfg.max_tokens

    def generate(self, prompt: str) -> str:
        resp = requests.post(
            f"{self.host}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                },
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        answer = data.get("response", "")
        return answer.strip()
