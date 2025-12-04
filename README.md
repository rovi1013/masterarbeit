# RAG Energieeffizienz-Evaluation

Dieses Repository enthält den praktischen Teil zu meiner Masterarbeit: 
**Nachhaltigkeit durch Effizienzsteigerung in Retrieval-Augmented Generation (RAG)-Systemen**

## Repository Struktur
```text
masterarbeit/
├── docker/                     # DOCKER
│   ├── Dockerfile/             # Docker Image
│   ├── docker-compose/         # Docker Compose
│   ├── .env                    # Environment Variablen
│   ├── entrypoint.sh           # Entrypoint Script
│   └── usage_scenario/         # GMT Usage Scenario
│
├── src/                        # SOURCE CODE
│   ├── app/                    # RAG App
│   │   ├── config              # Konfiguration des RAG-Systems
│   │   ├── api_server          # API Endpoint
│   │   ├── indexing            # Erstellen einer Datenbank aus Dokumenten
│   │   ├── retrieval           # Abruf aus Datenbank 
│   │   ├── prompt_template     # Prompt Template
│   │   ├── llm_client          # LLM (Ollama) Client
│   │   ├── rag_pipeline        # RAG-System
│   │   └── logging_config      # Logging
│   │
│   └── data/
│       ├── index/              # Kontext Datenbank
│       └── raw/                # Raw Dokumente
│
├── thesis/                     # Submodule Thesis (Overleaf-Sync)
├── requirements.txt
└── README.md
```

## Usage

### Über Docker
1. Indexing entweder vorher (über indexing.py) oder nach start über "docker exec rag-app python -m indexing.py"
2. docker compose up --build
3. Fragen an FastAPI /ask POST schicken

### Locally
1. Indexing über indexing.py
2. Starten des Systems über api_server.py
3. Fragen an FastAPI /ask POST schicken

## Notizen
Aktuelles Embedding Modell: sentence-transformers/all-MiniLM-L6-v2, [Dokumentation](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2). Wird beim indexing und retrieval (embedding der Frage) verwendet.

Aktuelle LLM (Generation): llama3:8b, [Dokumentation](https://ollama.com/library/llama3). Generiert aus der Frage und dem Kontext eine Antwort.

### "Chunking-Strategie"
Übersicht zur einfachen Chunking-Strategie mit dem aktellen Embedding Model:
- Embedding Model [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) verwendet einen 384-dimensionalen Vektorraum
- Bei aktueller Config (chunk_size=512, overlap=64) werden die 11 Dokumente in insgesamt 33.490 chunks eingeteilt
- Das sind dann `384 * 33.490 = 12.860.160` float-Werte
- Mit 4 Byte pro float-Wert sind das `12.860.160 * 4 Byte = 51.440.640 Byte`, also ungefähr 50 MB rein an Embeddings
- Dazu kommen noch die Roh-Text-Chunks, chromaDB spezifische Daten, etc.
- So werden aus 102 MB Dokumenten ungefähr 250 MB Embeddings

→ Viel Luft nach oben alleine beim Platzverbrauch über eine bessere Chunking-Strategie; Messungen zu Energieverbrauch folgen ...

### ChromaDB
[Dokumentation](https://docs.trychroma.com/docs/overview/introduction)

Eigentliche Embeddings (in /data/index/_random_uuid_/); siehe [Storage Layout](https://cookbook.chromadb.dev/core/storage-layout/):
- ``data_level0.bin`` (54.814 KB):  Contains the base layer of the hierarchical graph, storing the actual vectors and their connections.
- ``header.bin`` (1 KB): Holds metadata about the index, such as its parameters and structure details.
- ``index_metadata.pickle`` (980 KB): Chroma specific metadata about mapping between ids in embeddings table and labels in the HNSW (Hierarchical Navigable Small World) index.
- ``length.bin`` (131 KB): Records the number of links each node has, aiding in efficient traversal during searches.
- ``link_lists.bin`` (281 KB): Stores the adjacency lists for nodes, detailing their connections within the graph.

## RAG-System

3-Schritte System:
1. Indexing der Dokumente
2. Retrieval und Augmentation
3. Aufruf der LLM (Ollama)

Detaillierter Ablauf des RAG-Systems:
1. Indexing der Dokumente mit [indexing.py](src/app/indexing.py). Wird manuell und getrennt vom rest des Systems ausgeführt, da das Indexing nur einmal aufgerufen werden muss. Danach sind die Embedded Dokumente in der chromaDB gespeichert.
2. Aufruf der RAG-APP über API, konfiguriert in [api_server.py](src/app/api_server.py), mit einer Frage. Aktuell keine Konversation möglich, rein theoretisch einfach implementierbar, sorgt allerdings für unnötigen overhead und könnte die Messungen verfälschen. 
3. Weiterleitung der Frage an die "Zentrale" des RAG-Systems [rag_pipeline.py](src/app/rag_pipeline.py). Von hier wird das RAG-System gesteuert (Retrieval → Augmentation → Generation).
4. RETRIEVAL: Auf Basis der Frage, wird in [retrieval.py](src/app/retrieval.py) der Kontext aus der Datenbank geholt.
5. AUGMENTATION: Unter Verwendung des Prompt Templates ([prompt_template.py](src/app/prompt_template.py)) wird in [rag_pipeline.py](src/app/rag_pipeline.py) der finale Prompt erstellt. 
6. GENERATION: Der Prompt wird an den [llm_client.py](src/app/llm_client.py) weitergeleitet und die LLM (Modell definiert in [.env](docker/.env)) generiert eine passende Antwort auf Basis des Kontexts.
7. Antwort wird über FastAPI zusammen mit der Frage und dem Kontext zurückgesendet.

### indexing
Um das indexing über die GPU laufen zu lassen, ist in Windows der einfachste Weg das Script über docker zu starten:
```bash
docker compose run --rm rag-app python -m app.indexing
```

Pre-Condition des RAG-Systems, die Dokumente werden
1. Aufgeteilt (Chunking)
2. In eine chromaDB eingebettet (Embedding)
3. Datenbank ist fertig

Dadurch kann eine extra Messung nur für das Indexing durchgeführt werden.

### api_server
Öffnet über FastAPI einen POST endpoint zur Kommunikation mit der RAG-APP. Payload wird als JSON erwartet, erreichbar 
über 
```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "..."}'
```

### rag_pipeline
Managed das RAG-System (Retrieval → Augmentation → Generation):
1. Aufruf von retrieval mit der Frage
2. Kombination von Prompt Template, Kontext und Frage
3. Aufruf von LLM mit vollständigem Prompt
4. Return Dict mit ursprünglicher Frage, der Antwort und dem verwendeten Kontext

### retrieval
Auf Basis der Frage wird die chromDB durchsucht und die k-top passende Elemente werden zurückgegeben.

Die Frage muss dafür auch erst einmal embedded werden, dafür wird dasselbe SentenceTransformer Model verwendet, wie beim indexing. Außerdem wird das Model nur einmal in Memory geladen, sodass nur beim ersten Aufruf der Methode das Model geladen werden muss. **Wichtig für die Messungen**: Das erste Mal retrieval wird einige 100ms länger dauern als die danach folgenden in derselben Session.

### prompt_template
Einfach Template für den Prompt, der an die LLM weitergegeben wird, bestehend aus
- Kontext
- Frage

### llm_client
Verwendung von Ollama zum Self-Hosting der LLM (Unabhängigkeit). Separater Docker container wird zum Hosten der LLM verwendet, dadurch lassen sich die Messungen voneinander trennen. Die Last der LLM wird getrennt vom restlichen RAG-System. Der Docker container läuft über die GPU (siehe [Docker](#docker)).

Der OllamaClient leitet den vollständigen Prompt an die LLM weiter. Ollama bietet einige Konfigurationsmöglichkeiten, mit denen das Verhalten der LLM selbst gesteuert werden kann, wie die temperature oder num_predict (siehe [config](#config)).

### config
In [config.yaml](src/app/config.yaml) werden Konstanten gesetzt und die RAG-APP ruft diese über [config.py](src/app/config.py) auf.
- ``data_dir``: Verzeichnis der Raw Dokumente
- ``index_dir``: Verzeichnis der Embedded Dokumente
- ``embedding_model``: Model, welches zum embedden der Dokumente verwendet wird (aus Python Package sentence_transformers)
- ``embedding_device``: cpu oder gpu zum Ausführen des Embedding Models
- ``chunk_size``: Größe der Chunks (je nach Chunking Strategie auch dynamisch möglich)
- ``chunk_overlap``: Overlap zwischen den einzelnen Chunks (je nach Chunking Strategie auch dynamisch möglich)
- ``llm_host``: URL für Verbindung zu LLM
- ``llm_model``: Model, welches verwendet werden soll (hier nur die Defaulteinstellung, wird von Model in [.env](docker/.env) überschrieben)
- ``temperature``: Randomness/Kreativität der LLM-Antwort
- ``max_tokens``: Maximale Länge der Antwort
  - Weitere Konfigurationsmöglichkeiten der LLM sind unter anderem: mirostat, mirostat_eta, mirostat_tau, num_ctx, repeat_last_n, repeat_penalty, seed, stop, top_k, top_p, min_p (siehe [Dokumentation](https://docs.ollama.com/modelfile#valid-parameters-and-values))
- ``log_level``: Steuerung der Log-Nachrichten (DEBUG, INFO, WARNING, ERROR, etc.)

### simple_logging
Logging der App zum Debuggen.

## Docker
2 Services rag-app und ollama.

### Dockerfile für RAG-APP
Image basiert auf offiziellem [Python](https://hub.docker.com/_/python) Image (Version _python:3.12-slim_).

### rag-app service
Environment wird aus .env geladen

Environment Variablen:
- ``DATA_DIR``:
- ``INDEX_DIR``:
- ``OLLAMA_HOST``:
- ``OLLAMA_MODEL``:
- ``HF_HOME``: Setzt einen festen Ordner, an dem die Hugging Face Modelle gecached werden. Dadurch wird verhindert, dass die Modelle bei jedem Aufruf von [indexing.py](/src/app/indexing.py) neu heruntergeladen werden. Siehe [Dokumentation](https://huggingface.co/docs/huggingface_hub/package_reference/environment_variables#hfhome).
- ``ANONYMIZED_TELEMETRY`` (False): Verhindert das Senden von verschiedenen Informationen, ist hier hauptsächlich aus Performancegründen deaktiviert. Siehe [Dokumentation](https://docs.trychroma.com/docs/overview/telemetry)

Persistente Volumes:
- ``/src/data``: Die Datenbank der Embedded Dokumente sollte nicht jedes Mal neu erstellt werden
- ``/hf-cache``: Ordner für das Embedding Modell, muss nicht jedes Mal neu heruntergeladen werden

### ollama service
Extra Container für die LLM ermöglicht
- Ausführung des Models auf einer GPU
- getrennte Messungen vom restlichen RAG-System

Entrypoint-Script läd die konfigurierte LLM (in [.env](/docker/.env)) beim Starten des containers herunter, dadurch werden die Messungen nicht beeinflusst. 

Environment Variablen:
- ``OLLAMA_MODEL``: Welches Model soll verwendet werden (z.B. ``llama3:8b`` oder ``cas/teuken-7b-q4km``, [mehr](https://ollama.com/library?sort=popular))

## Test-Fragen.http
Alle Fragen liefern immer dieselbe Antwort, unter Verwendung der aktuellen Konfiguration und LLM.

Die Antwort auf Frage 4 ist besonders interessant:
```json
{
  "question": "Lässt sich der Klimawandel noch stoppen?",
  "answer": "Nein, aufgrund des Kontexts und der Angaben zum Wasserdampf als wichtigstem Treibhausgas kann man nicht mehr von einem Stillstand des Klimawandels sprechen. Der Klimawandel ist ein natürlicher Prozess, der sich durch den Anstieg des CO2-Gehalts in der Atmosphäre und andere Faktoren verstärkt hat. Es gibt keine Möglichkeit, ihn komplett zu stoppen.",
  "context": [
    "=== Wasserdampf ===\n[[Wasserdampf]] ist das wichtigste Treibhausgas.<ref name=\"Rahmstorf-APuZ-47-2007\">Stefan Rahmstorf: [https://www.bpb.de/apuz/30101/klimawandel-einige-fakten ''Klimawandel – einige Fakten.''] In: ''[[Aus Politik und Zeitgeschichte]].'' 47/2007.</ref> Sein Beitrag zum natürlichen Treibhauseffekt wird bei klarem Himmel auf etwa 60 % beziffert.<ref name=\"Kiehl et al. 1997\">J. T. Kiehl, K. E. Trenberth: ''Earth's annual global mean energy budget.'' In: ''[[American Meteorological Society]].'",
    "Periode]] sind und dabei nur selten einen weltweiten Einfluss ausübten. Zyklische Schwankungen werden auch als [[Klimafluktuation]]en bezeichnet, relativ rasche zyklische Wechsel auch als ''Klimaoszillation.''<ref>{{Internetquelle |url=http://www.spektrum.de/lexikon/geowissenschaften/klimafluktuation/8413 |titel=Klimafluktuation |werk=Lexikon der Geowissenschaften |hrsg=Spektrum akademischer Verlag |abruf=2016-08-12}}</ref> Eine Epoche vergleichsweise kühlen Klimas wird in dem Zusammenhang manchmal {{Anker|",
    "ugr/ugr_home/ugr_anwendungsgebiete/ugr_klima/ Klima und Klimawandel in den Umweltgesamtrechnungen] des [[Bundesministerium für Nachhaltigkeit und Tourismus|Bundesministeriums für Nachhaltigkeit und Tourismus]] und [[Bundesanstalt Statistik Österreich]]\n* [https://klimawandel.wald-rlp.de/ Klimawandel in den Wäldern von Rheinland-Pfalz] vom [[Ministerium für Umwelt, Energie, Ernährung und Forsten Rheinland-Pfalz]]\n* ''[https://interaktiv.morgenpost.de/klimawandel-hitze-meeresspiegel-wassermangel-stuerme-unbew",
    "== Die Erforschung des Klimawandels ==\n{{Hauptartikel|Forschungsgeschichte des Klimawandels}}\n\nSchon im 17. und 18. Jahrhundert wurde vereinzelt, wie zum Beispiel von dem Universalgelehrten [[Robert Hooke]], die Idee eines veränderlichen Klimas vertreten, begründet vor allem durch [[Fossil]]funde „tropischer“ Tiere und Pflanzen in gemäßigten Regionen Europas. Einen bedeutenden Fortschritt verzeichnete die beginnende Erforschung des Erdklimasystems durch die Arbeiten von [[Joseph Fourier|Jean Baptiste Joseph",
    "ttps://www.youtube.com/watch?v=y--V_SD_6LM |titel=Klima macht Geschichte (2): Von der Antike bis in die Gegenwart |hrsg=Story House Productions |datum=2015 |format=YouTube |abruf=2020-01-24 |abruf-verborgen=1 |kommentar=auch in der [https://www.zdf.de/dokumentation/terra-x/klima-macht-geschichte-2-108.html ZDF-Mediathek]}}\n* [https://www.climateactiontracker.org/ Climateactiontracker] (englisch) die Webseite der [[Climate Action Tracker]]\n* [https://iversity.org/de/courses/wie-man-den-klimawandel-leicht-ver"
  ]
}
```

Offensichtlich ist hier die Frage so perfekt formuliert, dass der ähnlichste Kontext irgendetwas mit Wasserdampf ist, was die LLM dann als wichtigstes Treibhausgas deklariert. Interessanterweise kommt bei genauerer Nachfrage zu Treibhausgasen (Frage 6) eine korrekte Antwort heraus. Ebenfalls so, beim Umformulieren der Frage (Frage 5). Hier einmal genauer in den Kontext schauen, der hier zurückgegeben wird, liefert eventuell mehr Erkenntnisse.

## Links

- [GMT Doku](https://docs.green-coding.io/docs/measuring/usage-scenario/)
- [LangChain RAG Tutorial](https://docs.langchain.com/oss/python/langchain/rag#expand-for-full-code-snippet)
- [LLM Generation Constants](https://pm.dartus.fr/posts/2025/how-llm-generate-text/)
- [Ollama Constants Erklärung](https://medium.com/@laurentkubaski/ollama-model-options-0eee31c902d3)
- [Ollama Constants offizielle Doku](https://docs.ollama.com/modelfile#valid-parameters-and-values)