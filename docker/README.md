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

### Image Details
Untersuchung des Docker Images ``docker-rag-app`` mit [dive](https://hub.docker.com/r/wagoodman/dive).

Informationen zum Image:
````shell
│ Image Details ├──────────────────────────────────────────────────────────────

Image name: docker-rag-app
Total Image size: 6.4 GB
Potential wasted space: 7.4 MB
Image efficiency score: 99 %
````

Image Layers:
````shell
│ Layers ├───────────────────────────────────────────────────────────────────── 
  Size  Command
 79 MB  FROM blobs
3.8 MB  RUN /bin/sh -c set -eux;
 37 MB  RUN /bin/sh -c set -eux;
   0 B  RUN /bin/sh -c set -eux;
 37 MB  RUN /bin/sh -c apt-get update && apt-get install -y curl # buildkit 
   0 B  WORKDIR /src
 145 B  COPY ../requirements.txt /src/requirements.txt # buildkit
6.3 GB  RUN /bin/sh -c pip install --no-cache-dir -r requirements.txt # buildkit
 26 kB  COPY ../src/app /src/app # buildkit 
````

Größter Teil des Speicherplatzverbrauchs sind die Python Packages:
````shell
│ Current Layer Contents ├──────────────────────────────────────────────────────
Permission     UID:GID       Size  Filetree
drwxr-xr-x         0:0     6.4 GB  ├── usr
drwxr-xr-x         0:0     6.3 GB  │   ├── local
drwxr-xr-x         0:0     6.3 GB  │   │   ├── lib
drwxr-xr-x         0:0     6.3 GB  │   │   │   ├── python3.12
drwxr-xr-x         0:0     6.3 GB  │   │   │   │   ├── site-packages
drwxr-xr-x         0:0     2.8 GB  │   │   │   │   │   ├─⊕ nvidia
drwxr-xr-x         0:0     1.6 GB  │   │   │   │   │   ├─⊕ torch
drwxr-xr-x         0:0     564 MB  │   │   │   │   │   ├─⊕ triton
drwxr-xr-x         0:0     237 MB  │   │   │   │   │   ├─⊕ cusparselt
drwxr-xr-x         0:0     153 MB  │   │   │   │   │   ├─⊕ pyarrow
drwxr-xr-x         0:0     109 MB  │   │   │   │   │   ├─⊕ scipy
drwxr-xr-x         0:0     107 MB  │   │   │   │   │   ├─⊕ transformers
drwxr-xr-x         0:0      69 MB  │   │   │   │   │   ├─⊕ sympy
drwxr-xr-x         0:0      68 MB  │   │   │   │   │   ├─⊕ pandas
drwxr-xr-x         0:0      55 MB  │   │   │   │   │   ├─⊕ chromadb_rust_bindin
drwxr-xr-x         0:0      54 MB  │   │   │   │   │   ├─⊕ onnxruntime
drwxr-xr-x         0:0      44 MB  │   │   │   │   │   ├─⊕ sklearn
drwxr-xr-x         0:0      40 MB  │   │   │   │   │   ├─⊕ numpy
````

### Anpassungen für GMT
In GMT können keine Volumes im Docker Compose definiert werden. Daher werden bereits in [Dockerfile.gmt](../Dockerfile.gmt) alle Daten und Dokumente ins Image geladen. Der Unterschied zum Standard-Dockerfile sind 3 zusätzliche ``COPY`` Anweisungen.

|                | Dockerfile | Dockerfile.gmt |
|:---------------|:-----------|:---------------|
| **Image Size** | 6.4 GB     | 10 GB          |

Zusätzlicher Layer (mit [dive](https://hub.docker.com/r/wagoodman/dive)):
````shell
│ Layers ├─────────────────────────────────────────────────────────────────────
  Size  Command
3.5 GB  COPY src/data /src/data # buildkit
112 kB  COPY src/scripts /src/scripts # buildkit
 92 MB  COPY emb_models /emb_models # buildkit 
````
Nur so groß, wenn Datenbank in ``src/data/`` bereits existiert. Bei Messungen mit GMT existiert die Datenbank nicht, daher ist der zusätzliche Speicherplatzverbrauch vernachlässigbar; ungefähr 100 MB.

## rag-app Service
Jeder Systemparameter in [config.yaml](../src/app/config.yaml) kann durch eine gleichnamige, all-uppercase Umgebungsvariable überschrieben werden. Bsp.: ``llm_model`` → ``LLM_MODEL``.

**Zusätzliche Environment Variablen:**
- ``HF_HOME``: Cache für Hugging Face (HF)
- ``ANONYMIZED_TELEMETRY``: Keine Telemetriedaten senden ([Chroma Doku](https://docs.trychroma.com/docs/overview/telemetry)); sorgt für unnötigen clutter im Logging 
- ``RAG_PRINT_RESPONSES``: Ausgabe von [rag_querries.py](../src/scripts/rag_querries.py) toggeln (0/1)

**Volumes:**
- ``/src/data``: Speicherort von Dokumenten und Vektordatenbank
- ``/src/scripts``: Speicherort der Skripte: Datensatz download und RAG Anfragen
- ``/hf-cache``: Cache für HF
- ``/logs``: Logging
- ``/emb_models``: Speicherort der Sentence-Transformer Modelle

### Anpassungen für GMT
GMT erlaubt keine Volumes (siehe [Dockerfile](#dockerfile-für-rag-app)). Umgebungsvariablen können vor einem Messlauf mit GMT-Variablen überschireben werden; nach dem Schema: ``<VAR_NAME>`` → ``__GMT_VAR_<VAR_NAME>__``. Deployment über NVIDIA Grafikkarte: von ``deploy.resources.reservarions.devices: ...`` zu ``docker-run-args``: ``--gpu=all``. Bei GMT Messlauf können in ``docker-run-args`` zusätzliche Aufrufparameter gesetzt werden.

_Anpassungen des ollama Service folgen demselben Schema._


## ollama Service
Extra Container für die LLM ermöglicht
- Ausführung des Models auf einer GPU
- getrennte Messungen vom restlichen RAG-System

Entrypoint-Script läd die konfigurierte LLM beim Starten des containers herunter, dadurch werden die Messungen nicht beeinflusst. 

Environment Variablen:
- ``OLLAMA_MODEL``: Welche LLM soll verwendet werden (z.B. ``llama3:8b`` oder ``cas/teuken-7b-q4km``, [mehr](https://ollama.com/library?sort=popular)), muss auf GMT verfügbar sein und dieselbe wie in [config.yaml](../src/app/config.yaml).


## Container in GMT
Die Ausführung auf der GMT Testbench erfordert das eine ``usage_scenario`` Datei. Hier wird ein bestimmter Workflow festgelegt, der auf der Testbench ausgeführt wird. Die Orchestrierung der Container erfolgt in GMT über ``docker run`` mit den Parametern aus der Docker Compose Datei. 

Beispiel für den ``rag-app`` Service:
````shell
docker run -it -d --name rag-app -v /tmp/green-metrics-tool/repo:/tmp/repo:ro --gpus=all -e HF_HOME=/root/.cache/huggingface -e ANONYMIZED_TELEMETRY=False -e RAG_PRINT_RESPONSES=0 --net GMT_default_tmp_network_7032493 --cpuset-cpus 1,2,3,4,5 --cpus=5 --oom-score-adj=1000 --memory=15718918144 --env=GMT_CONTAINER_MEMORY_LIMIT=15718918144 --memory-swap=15718918144 ragapp_6151630_gmt_run_tmp
````

Zusätzlich wurden am Dockerfile und der Docker Compose kleine Änderungen für GMT vorgenommen. [docker-compose.gmt.yaml](../docker-compose.gmt.yml) und [Dockerfile.gmt](../Dockerfile.gmt) sind die angepassten Versionen.
