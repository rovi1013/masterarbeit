# Retrieval Augmented Generation Assessment (RAGAS)

RAGAS ist ein Framework zur automatisierten Evaluation von RAG-Systemen.

## Referenzen
[**RAGAS Dokumentation**](https://docs.ragas.io/en/stable/)

[**RAGAS Paper**](https://arxiv.org/abs/2309.15217)

## Struktur
````text
eval-ragas/
├── ragas-data/                         # MESSLAUF DATEN
│   └── <ID>_answers_eval.json.gz       # Metriken der RAGAS Evaluation
│
├── scripts/                            # RAGAS WORKFLOW
│   ├── get_rag_answers                 # Holt Antworten der RAG API
│   └── ragas_evaluation                # Evaluiere Antworten mit RAGAS
│
├── questions.jsonl                     # Fragekatalog
├── requirements.txt
└── README.md
````


## Workflow
1. Prerequisits
2. RAG App starten
3. RAG API aufrufen
4. Evaluation mit RAGAS

### Prerequisites
Setup des Python VENV und installation der Python Packages:
````shell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
````

### RAG App ausführen
Schritte 1. - 5. aus [RAG App Dokumentation](../README.md) ausführen, inklusive des Warmups für die RAG App.

### RAG API aufrufen
Das Skript [get_rag_answers.py](#rag-api-antworten) ruft die API der RAG App mit dem Fragekatalog [questions.json](questions.json) auf, die Ergebnisse werden in [ragas-data/](ragas-data) als JSON mit dem Format ``YYYY-MM-DD_<GMT RUN ID>_answers.json`` gespeichert.
````shell
python .\scripts\get_rag_answers.py --run-id "<GMT RUN ID>" --date "YYYY-MM-DD"
````

### Evaluation mit RAGAS
Das Skript [ragas_evaluation.py](#ragas-evaluation) verwendet das Framework RAGAS, um die Antworten der RAG App zu evaluieren, die Ergebnisse werden in [ragas-data/](ragas-data) als GZIP komprimierte JSON mit dem Format ``YYYY-MM-DD_<GMT RUN ID>_answers_eval.json.gz`` gespeichert.
````shell
python .\scripts\ragas_evaluation.py --input ".\ragas-data\YYYY-MM-DD_<GMT RUN ID>_answers.json"
````


## Skripts

### RAG API Antworten

````shell
usage: get_rag_answers.py [-h] -r RUN_ID -d DATE

Lade Antworten der RAG API für RAGAS Messungen.

options:
  -h, --help           show this help message and exit
  -r, --run-id RUN_ID  Dazugehörige GMT Messlauf ID.
  -d, --date DATE      Datum des Messlaufs YYYY-MM-DD (gleich wie GMT).
````

### RAGAS Evaluation

````shell
usage: ragas_evaluation.py [-h] -i INPUT

Evaluation der RAG Antworten mit RAGAS.

options:
  -h, --help         show this help message and exit
  -i, --input INPUT  Pfad zu *_answers.json.
````