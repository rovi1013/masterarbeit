# Retrieval Augmented Generation Assessment (RAGAS)

RAGAS ist ein Framework zur automatisierten Evaluation von RAG-Systemen.

## Referenzen
[**RAGAS Dokumentation**](https://docs.ragas.io/en/stable/)

[**RAGAS Paper**](https://arxiv.org/abs/2309.15217)

## Struktur
````text
eval-ragas/
├── ragas-data/                         # MESSLAUF DATEN
│   ├── <ID>_predictions.jsonl          # ...
│   └── <ID>_ragas_scores.jsonl         # ...
│
├── scripts/                            # RAGAS WORKFLOW
│   ├── 
│   └── 
│
├── questions.jsonl                     # Fragekatalog
├── requirements.txt
└── README.md
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