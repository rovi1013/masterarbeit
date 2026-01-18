# RAG Energieeffizienz-Evaluation

Dieses Repository enthält den praktischen Teil zur Masterarbeit: 
**Nachhaltigkeit durch Effizienzsteigerung in Retrieval-Augmented Generation (RAG)-Systemen**

## Lizenz
Der Code ist lizensiert unter der MIT-Lizenz. Inhalte Dritter sind unter LICENSES.md dokumentiert.

## Repository Struktur
```text
masterarbeit/
├── docker/                     # DOCKER
│   ├── Dockerfile/             # Docker Image
│   ├── docker-compose/         # Docker Compose
│   ├── .env                    # Environment Variablen
│   ├── entrypoint.sh           # Entrypoint Script
│   └── Test-Frage.http         # Test für RAG-APP
│
├── eval-gmt/                   # GREEN METRICS TOOL
│   └── README.md
│
├── eval-ragas/                 # RAGAS FRAMEWORK
│   └── README.md
│
├── src/                        # SOURCE CODE & DATA
│   ├── app/                    # RAG-APP
│   │   ├── config              # Konfiguration des RAG-Systems
│   │   ├── api_server          # API Endpoint
│   │   ├── embedding           # Lade sentence-transformer model
│   │   ├── indexing            # Erstellen einer Datenbank aus Dokumenten
│   │   ├── retrieval           # Abruf aus Datenbank 
│   │   ├── prompt_template     # Prompt Template
│   │   ├── llm_client          # LLM (Ollama) Client
│   │   ├── simple_logging      # Logging
│   │   ├── warmup_indexing     # Warmup Script Indexing
│   │   └── warmup_rag          # Warmup Script RAG-APP
│   │
│   ├── data/
│   │   ├── index/              # Kontext Datenbank
│   │   └── raw/                # Raw Dokumente
│   │
│   └── scripts/
│       └── rag_querries.sh     # Fragekatalog für die RAG API
│
├── emb_models/                 # Embedding Models Cache
├── hf-cache/                   # Hugging Face Cache
├── logs/                       # Logging
├── usage_scenario.yaml         # GMT Usage Scenario
├── docker-compose.gmt.yml      # GMT Docker Compose
├── Dockerfile.gmt              # GMT Dockerfile
├── requirements.txt            # Python Packages
├── LICENSES.md                 # Datensatz (src/data/raw/) Lizenzinformationen
└── README.md
```

## Usage

1. Docker container starten (+ Image bauen):
```shell
docker compose up --build
```
2. Indexing Warmup starten:
```shell
docker exec rag-app python -m app.warmup_indexing
```
3. [MESSUNG] Indexing ausführen:
```shell
docker exec rag-app python -m app.indexing
```
4. RAG-APP Warmup starten:
```shell
docker exec rag-app python -m app.warmup_rag
```
5. [MESSUNG] Lasttest auf RAG-APP ausführen ...


## NEXT UP / TODO

### Vorschläge aus Envite Meeting
* Indexing: Dateien in Markdown konvertieren und dann chunken
* LLM Frage ummformulieren lassen, um die Fragen umzuformulieren und dann die besten Ergebnisse aus den Abfragen als Kontext verwenden
* Tabellen und Zahlen aus Kontext explizit abfragen zum Testen (Evaluation)
* Kleine Infos dirket mal in den Slack Channel

### Ollama Client
TODO: Erste Anfrage vor Messungen durchführen.

Aktuell dauert die erste Anfrage (trotz warmup) an Ollama Host immer noch länger als darauf folgende. Aber Antwortzeit der ersten Anfrage ist durch das warmup schon reduziert.


## Notizen
Aktuelles Embedding Modell: sentence-transformers/all-MiniLM-L6-v2, [Dokumentation](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2). Wird beim indexing und retrieval (embedding der Frage) verwendet.

Aktuelle LLM (Generation): llama3:8b, [Dokumentation](https://ollama.com/library/llama3). Generiert aus der Frage und dem Kontext eine Antwort.

### sentence_transformers backend
Bietet die Wahl eines (aus 3) Backends für Sentence Transformers zu nutzen. Default ist PyTorch, für GPU sollte ich mir ONNX anschauen und OpenVINO bietet Beschleunigungen für die CPU (nicht so interessant). So kann die Inferenz der Modelle beschleunigt werdern. Siehe [Dokumentation](https://sbert.net/docs/sentence_transformer/usage/efficiency.html).

### "Chunking-Strategie"
Übersicht zur einfachen Chunking-Strategie (siehe [indexing.py](src/app/indexing.py), Zeile 76 ff., simple_chunk()) mit dem aktellen Embedding Model:
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

### Sprachsensitives Retrieval
Bei Fragen auf Deutsch werden die (deutschen) Wikipedia Artikel den (englischen) PDF Dokumenten bevorzugt. Das liegt daran, dass keine Unterscheidung zwischen verschiedenen Sprachen beim embedding oder retrieval stattfindet. Das führt dazu, dass die englischen PDFs viel seltener in der Ähnlichkeitsüberprüfung in retrieval zu den top-k Ergebnissen zählen. Wenn man sich die top-k Dokumente anschaut, ist bei der deutschen Version der korrekte chunk (chunk 0) des Dokuments EnergyandAI.pdf nicht dabei. Der Name 'World Energy Outlook Special Report\nEnergy and AI\nIEA. CC BY 4.0' wird verwendet, damit zumindest immer das richtige Dokument gefunden wird.

Mit Deutsch "Länder" (countries) in der Frage:
```json
{
    "question": "Welche Länder werden erwähnt in 'World Energy Outlook Special Report\nEnergy and AI\nIEA. CC BY 4.0'?",
    "answer": "Keine Länder werden in diesem speziellen Bericht der Internationalen Energieagentur (IEA) erwähnt. Der Bericht konzentriert sich auf die Rolle von Artificial Intelligence (AI) im Energiesektor und nicht auf bestimmte Länder.",
    "context": [
        " Energy Data Centre provided assistance \nthroughout the preparation of the report.  Valuable input to the analysis and drafting was \nprovided by George Kamiya (independent consultant). \nIEA. CC BY 4.0\n \n6 International Energy Agency | Energy and AI  \n \nThe work could not have been completed without the support and co-operation provided by \nmany government bodies, organisations and companies worldwide,  notably contributions \nfrom: Google, Iberdrola, Microsoft , ReNew, Schneider Electric  (S ustainability Re",
        "ers \nfrom government, the tech sector and the energy industry. \nPeer reviewers \nMany senior government officials and international experts provided input and reviewed \npreliminary drafts of the report. Their comments and suggestions were of great value. They \ninclude: \nAbhijit Abhyankar Indian Institute of Technology Delhi \nSara Axelrod Crusoe \nHarmeet Bawa Hitachi Energy \nAnna Blomborg Alfa Laval  \nJohannes Böhner Tennet \nMatthew Carr Luffy.ai \nJohn Catillaz GE Vernova \nAlexandre Catta Department of Natura",
        "Papadimoulis, Jules Sery and Richard Simon. \nIEA. CC BY 4.0.\n \n6 International Energy Agency | World Energy Outlook 2025 \n \nOther contributors from across the IEA were:  Heymi Bahar, Cerstin Berner, Lena Brun, Eren \nÇam, Eleonora Chiarati , Joel Couse, Leïlou Daunit, Pierre Demey, Musa Erdogan, Carlos \nFernández Alvarez, Ciarán Healy, Alexandra Hegarty, Gyubin Hwang, Tomoya  Iwaki, Akos \nLosz, David Martin, Jacob Messing, Gergely Molnár , Jeremy Moorhouse, Quentin Paletta , \nAndrea Pronzati, Anna Sagués Mol",
        "falt beruhenden globalen 100-Prozent-erneuerbare-Energien-System, welches ohne negative CO<sub>2</sub>-Emissionstechnologien auskommt. Dabei werden die Bereiche Strom, Wärme, Verkehr und Meerwasserentsalzung bis 2050 betrachtet.<ref>{{Internetquelle |url=http://energywatchgroup.org/globales-energiesystem-mit-100-erneuerbaren-energien |titel=Neue Studie: Globales Energiesystem mit 100% Erneuerbaren Energien |werk=energywathgroup.org |archiv-url=https://web.archive.org/web/20220305095734/https://www.energywat",
        "times as much.  \nPolicy makers and markets have lacked the tools to assess implications \nThe energy sector is therefore at the heart of one of  the most important technological \nrevolutions today. However, there is still a lack of understanding of the  stakes and  \nimplications of this deepening connection between energy and AI. Consistent with its strong \ntrack record of identifying and exploring  emerging issues in the energy sector, th is new  \nInternational Energy Agency (IEA)  special report seeks to f"
    ]
}
```
Retrived Docs:
```shell
2026-01-08 14:20:03 [DEBUG] app.retrieval: hit#1: source=/src/data/raw/EnergyandAI.pdf chunk=21 dist=0.5956
2026-01-08 14:20:03 [DEBUG] app.retrieval: hit#2: source=/src/data/raw/EnergyandAI.pdf chunk=23 dist=0.5990
2026-01-08 14:20:03 [DEBUG] app.retrieval: hit#3: source=/src/data/raw/WorldEnergyOutlook2025.pdf chunk=20 dist=0.6038
2026-01-08 14:20:03 [DEBUG] app.retrieval: hit#4: source=/src/data/raw/Erneuerbare Energie - Wikipedia.txt chunk=322 dist=0.6073
2026-01-08 14:20:03 [DEBUG] app.retrieval: hit#5: source=/src/data/raw/EnergyandAI.pdf chunk=58 dist=0.6093
```

Mit Englisch "Länder" (countries) in der Frage:
```json
{
    "question": "Welche countries werden erwähnt in 'World Energy Outlook Special Report\nEnergy and AI\nIEA. CC BY 4.0'?",
    "answer": "Die folgenden Länder werden im \"World Energy Outlook Special Report: Energy and AI\" erwähnt:\n\n* Australia\n* Austria\n* Belgium\n* Canada\n* Czech Republic\n* Denmark\n* Estonia\n* Finland\n* France\n* Germany\n* Greece\n* Hungary\n* Ireland\n* Italy\n* Japan\n* Korea\n* Latvia\n* Lithuania\n* Luxembourg\n* Mexico\n* Netherlands\n* New Zealand\n* Norway\n* Poland\n* Portugal\n* Republic of Türkiye\n* United Kingdom\n* United States",
    "context": [
        "World Energy Outlook Special Report\nEnergy and AI\nIEA. CC BY 4.0\nINTERNATIONAL ENERGY\nAGENCY\nIEA Member \ncountries:    \nAustralia    \nAustria   \nBelgium\nCanada\nCzech Republic \nDenmark\nEstonia\nFinland \nFrance \nGermany \nGreece \nHungary\nIreland \nItaly\nJapan\nKorea\nLatvia\nLithuania \nLuxembourg \nMexico \nNetherlands \nNew Zealand \nNorway\nPoland \nPortugal \nSlovak Republic \nSpain \nSweden \nSwitzerland \nRepublic of Türkiye \nUnited Kingdom \nUnited States\nThe European \nCommission also \nparticipates in the \nwork of the IE",
        "n:  Austria, Belgium, Bulgaria, Croatia, Cyprus 1,2, Czech Republic, Denmark, \nEstonia, Finland, France, Germany, Greece, Hungary, Ireland, Italy, Latvia, Lithuania, \nLuxembourg, Malta, Netherlands, Poland, Portugal, Romania, Slovak Republic, Slovenia, \nSpain and Sweden. \nIEA (International Energy Agency):   Australia, Austria, Belgium, Canada, Czechia, Denmark, \nEstonia, Finland, France, Germany, Greece, Hungary, Ireland, Italy, Japan, Korea, Latvia, \nLithuania, Luxembourg, Mexico, New Zealand, Norway, Pol",
        ". CC BY 4.0.\n \n490 International Energy Agency | World Energy Outlook 2025 \n \nRegional and country groupings \nAdvanced economies:  O rganisation for Economic Co -operation and Development (OECD)  \ngrouping and Bulgaria, Croatia, Cyprus1,2, Malta and Romania. \nAfrica:  North Africa and sub-Saharan Africa regional groupings. \nAsia Pacific:   Southeast Asia regional grouping and Australia, Bangladesh, Democratic \nPeople’s Republic of Korea (North Korea), India, Japan, Korea, Mongolia, Nepal, New Zealand, \nPaki",
        "ca. OECD/IEA, Paris, France, 237 pp.\nIEA, 2017: World Energy Outlook 2017. Flagship Report, November 2017, IEA, \nParis, France.\nIEA, 2018: World Energy Balances 2018. In: International Energy Agency, \nOECD/IEA, Paris, France.\nIEA, 2019a: World Energy Investment 2019. Flagship Report, May 2019. \nOECD, Paris, France 176 pp.\nIEA, 2019b: Securing Investments in Low-Carbon Power Generation Sources. \nOECD, Paris, 16 pp.\nIEA, 2019c: Africa Energy Outlook 2019. 288 pp. https://www.iea.org/reports/\nafrica-energy-out",
        "r, Iceland, Israel 5, Kosovo, Montenegro, North Macedonia, Norway, Republic of \nMoldova, Serbia, Switzerland, Türkiye, Ukraine and United Kingdom. \nEuropean Union:  Austria, Belgium, Bulgaria, Croatia, Cyprus 1,2, Czech Republic, Denmark, \nEstonia, Finland, France, Germany, Greece, Hungary, Ireland, Italy, Latvia, Lithuania, \nLuxembourg, Malta, Netherlands, Poland, Portugal, Romania, Slovak Republic, Slovenia, \nSpain and Sweden. \nIEA (International Energy Agency) : Australia, Austria, Belgium, Canada, Czech"
    ]
}
```

Retrieved Docs:
```shell
2026-01-08 14:14:22 [DEBUG] app.retrieval: hit#1: source=/src/data/raw/EnergyandAI.pdf chunk=0 dist=0.4574
2026-01-08 14:14:22 [DEBUG] app.retrieval: hit#2: source=/src/data/raw/WorldEnergyOutlook2025.pdf chunk=2730 dist=0.5339
2026-01-08 14:14:22 [DEBUG] app.retrieval: hit#3: source=/src/data/raw/WorldEnergyOutlook2025.pdf chunk=2726 dist=0.5589
2026-01-08 14:14:22 [DEBUG] app.retrieval: hit#4: source=/src/data/raw/IPCC_AR6_WGIII_FullReport.pdf chunk=21446 dist=0.5734
2026-01-08 14:14:22 [DEBUG] app.retrieval: hit#5: source=/src/data/raw/EnergyandAI.pdf chunk=1582 dist=0.5993
```


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
docker exec rag-app python -m app.indexing
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

### embedding
Lade ein SentenceTranformer Model, das Text embedden kann. Wenn möglich wird das Model auf einer GPU (cuda) ausgeführt, wenn nicht auf der CPU. Modelle werden in [emb_models](emb_models) gespeichert. Siehe [Dokumentation](https://sbert.net/docs/sentence_transformer/usage/efficiency.html) zur Wahl eines Backends zur Effizienzsteigerung (z.B. ONNX).

### llm_client
Verwendung von Ollama zum Self-Hosting der LLM (Unabhängigkeit). Separater Docker container wird zum Hosten der LLM verwendet, dadurch lassen sich die Messungen voneinander trennen. Die Last der LLM wird getrennt vom restlichen RAG-System. Der Docker container läuft über die GPU (cuda) (siehe [Docker](#docker)).

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
- ``DATA_DIR``: Ordner der Raw Dokumente.
- ``INDEX_DIR``: Ordner der Embedded Dokumente (Vektordatenbank).
- ``OLLAMA_HOST``: Die Addresse, unter der Ollama gehostet wird.
- ``OLLAMA_MODEL``: Das zu verwendente Ollama Model, wird in [.env](docker/.env) oder in [config.yaml](src/app/config.yaml) festgelegt.
- ``LOG_DIR``: Logging Dateien werden hier abgespeichert.
- ``EMBEDDING_MODEL_DIR``: Setzt einen festen Ordner, an dem die sentence-transformer Modelle gecached werden. Dadurch wird verhindert, dass die Modelle bei jedem Aufruf von [embedding.py](src/app/embedding.py) neu heruntergeladen werden.
- ``HF_HOME``: Lokaler Hugging Face Cache; Siehe [Dokumentation](https://huggingface.co/docs/huggingface_hub/package_reference/environment_variables#hfhome).
- ``ANONYMIZED_TELEMETRY`` (False): Verhindert das Senden von verschiedenen Informationen, ist hier hauptsächlich aus Performancegründen deaktiviert. Siehe [Dokumentation](https://docs.trychroma.com/docs/overview/telemetry)

Persistente Volumes:
- ``/src/data``: Die Datenbank der Embedded Dokumente sollte nicht jedes Mal neu erstellt werden
- ``/hf-cache``: Ordner für das Embedding Modell, muss nicht jedes Mal neu heruntergeladen werden
- ``/logs``: Logging.
- ``/emb_models``: Speicherort für die sentence-transformer Modelle.

### ollama service
Extra Container für die LLM ermöglicht
- Ausführung des Models auf einer GPU
- getrennte Messungen vom restlichen RAG-System

Entrypoint-Script läd die konfigurierte LLM (in [.env](/docker/.env)) beim Starten des containers herunter, dadurch werden die Messungen nicht beeinflusst. 

Environment Variablen:
- ``OLLAMA_MODEL``: Welches Model soll verwendet werden (z.B. ``llama3:8b`` oder ``cas/teuken-7b-q4km``, [mehr](https://ollama.com/library?sort=popular))

## Test-Fragen.http
Alle Fragen liefern immer dieselbe Antwort, unter Verwendung der aktuellen Konfiguration und LLM (Commit vom 09.12.2025).

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