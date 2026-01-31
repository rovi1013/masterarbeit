# Virtualisierung via Docker

Dieser Arbeit verwendet 2 seperate Services: rag-app und ollma. Wobei der ollama service einfach nur ein offizielles Docker Image ist ([Link](https://hub.docker.com/r/ollama/ollama)). Der rag-app service basiert auf einem Python Image und wird in [Dockerfile](Dockerfile) konfiguriert. 


## Struktur
````text
masterarbeit/
├── docker/                     # LOKALE AUSFÜHRUNG
│   ├── .env                    # Environment Variablen
│   ├── docker-compose.yml      # Docker Compose
│   ├── Dockerfile              # Docker Image
│   ├── entrypoint.sh           # Entrypoint Script
│   └── Test-Fragen.http        # Test für RAG-APP
│
├── docker-compose.gmt.yml      # GMT Docker Compose
├── Dockerfile.gmt              # GMT Dockerfile
└── usage_scenario.yaml         # GMT Usage Scenario
````


## Dockerfile für RAG-APP
Image basiert auf offiziellem [Python](https://hub.docker.com/_/python) Image mit der Version _python:3.12-slim_ und dem Digest ``sha256:d75c4b6cdd039ae966a34cd3ccab9e0e5f7299280ad76fe1744882d86eedce0b``. Durch den Digest kann immer sichergestellt werden, dass das exakt selbe Image von Docker Hub geladen wird.


## rag-app service
Environment wird aus .env geladen

Environment Variablen:
- ``DATA_DIR``: Ordner der Raw Dokumente.
- ``INDEX_DIR``: Ordner der Embedded Dokumente (Vektordatenbank).
- ``OLLAMA_HOST``: Die Addresse, unter der Ollama gehostet wird.
- ``OLLAMA_MODEL``: Das zu verwendente Ollama Model, wird in [config.yaml](../src/app/config.yaml) festgelegt.
- ``LOG_DIR``: Logging Dateien werden hier abgespeichert.
- ``EMBEDDING_MODEL_DIR``: Setzt einen festen Ordner, an dem die sentence-transformer Modelle gecached werden. Dadurch wird verhindert, dass die Modelle bei jedem Aufruf von [embedding.py](src/app/embedding.py) neu heruntergeladen werden.
- ``HF_HOME``: Lokaler Hugging Face Cache; Siehe [Dokumentation](https://huggingface.co/docs/huggingface_hub/package_reference/environment_variables#hfhome).
- ``ANONYMIZED_TELEMETRY`` (False): Verhindert das Senden von verschiedenen Informationen, ist hier hauptsächlich aus Performancegründen deaktiviert. Siehe [Dokumentation](https://docs.trychroma.com/docs/overview/telemetry)

Persistente Volumes:
- ``/src/data``: Die Datenbank der Embedded Dokumente sollte nicht jedes Mal neu erstellt werden, sondern nur, wenn es gewollt ist.
- ``/hf-cache``: Ordner für das Embedding Modell, muss nicht jedes Mal neu heruntergeladen werden
- ``/logs``: Logging.
- ``/emb_models``: Speicherort für die sentence-transformer Modelle.


## ollama service
Extra Container für die LLM ermöglicht
- Ausführung des Models auf einer GPU
- getrennte Messungen vom restlichen RAG-System

Entrypoint-Script läd die konfigurierte LLM beim Starten des containers herunter, dadurch werden die Messungen nicht beeinflusst. 

Environment Variablen:
- ``OLLAMA_MODEL``: Welches Model soll verwendet werden (z.B. ``llama3:8b`` oder ``cas/teuken-7b-q4km``, [mehr](https://ollama.com/library?sort=popular))


## Container in GMT
Die Ausführung auf der GMT Testbench erfordert das [usage_scenario.yml](../usage_scenario.yml). Hier wird ein bestimmter Workflow festgelegt, der auf der Testbench ausgeführt wird.

Zusätzlich wurden am Dockerfile und der Docker Compose kleine Änderungen für GMT vorgenommen. [docker-compose.gmt.yaml](../docker-compose.gmt.yml) und [Dockerfile.gmt](../Dockerfile.gmt) sind die angepassten Versionen.
