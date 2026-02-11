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
Das Skript [get_rag_answers.py](#rag-api-antworten) ruft die API der RAG App auf, die Ergebnisse werden in [ragas-data/](ragas-data) gespeichert.
````shell
python .\scripts\get_rag_answers.py --run-id "<GMT RUN ID>" --date "YYYY-MM-DD"
````

### Evaluation mit RAGAS (lokal/remote)
**(LOKAL)** Das Skript [ragas_evaluation.py](#ragas-evaluation-lokalremote) verwendet das Framework RAGAS, um die Antworten der RAG App lokal zu evaluieren.
````shell
python .\scripts\ragas_evaluation.py --input ".\ragas-data\YYYY-MM-DD_<GMT RUN ID>_answers.json"
````

**(REMOTE)** Das Skript [ragas_eval_remote.py](#ragas-evaluation-lokalremote) verwendet das Framework RAGAS, um die Antworten der RAG App remote zu evaluieren.
````shell
python .\scripts\ragas_eval_remote.py --input ".\ragas-data\YYYY-MM-DD_<GMT RUN ID>_answers.json" --open-api-key "<OPEN API KEY>"
````


## Skripts

### RAG API Antworten
Das Skript [get_rag_answer.py](scripts/get_rag_answers.py) ruft die RAG-App API mit dem Fragekatalog auf, der auch für die GMT Messläufe verwendet wird in [src/scripts/questions.json](../src/scripts/questions.json). Die Antworten als JSON mit dem Format ``YYYY-MM-DD_<GMT RUN ID>_answers.json`` gespeichert.

````shell
usage: get_rag_answers.py [-h] -r RUN_ID -d DATE

Lade Antworten der RAG API für RAGAS Messungen.

options:
  -h, --help           show this help message and exit
  -r, --run-id RUN_ID  Dazugehörige GMT Messlauf ID.
  -d, --date DATE      Datum des Messlaufs YYYY-MM-DD (gleich wie GMT).
````

Das Schema der gespeicherten Antworten sieht so aus:
````json
{
  "meta": {
    "run_id": "<GMT RUN ID>",
    "run_date": "YYYY-MM-DD",
    "api_url": "http://localhost:8000/ask"
  },
  "records": [
    {
      "q_id": "q_id von questions.json",
      "question": "question von questions.json",
      "answer": "Antwort der LLM",
      "contexts": [
        "context_1",
        "context_2",
        "...",
        "context_N"
      ],
      "context_meta": [
        {
          "source": "Dokumentenpfad von context_1",
          "chunk_index": Chunk Nummer von context_1,
          "type": "Dokumententyp von context_1"
        },
        "..."
      ],
      "gold_doc": "Dokument, aus dem die Frage generiert wurde, von questions.json",
      "ground_truth": "Die Ground Truth Antwort, von questions.json",
      "error": "Aktuell nichts"
    },
    "..."
  ]
}
````

### RAGAS Evaluation (lokal/remote)
**(LOKAL)** Das Skript [ragas_evaluation.py](scripts/ragas_evaluation.py) verwendet das Framework RAGAS, um die Antworten der RAG App aus ``YYYY-MM-DD_<GMT RUN ID>_answers.json`` zu evaluieren. Der Judge ist eine lokale LLM, die über den Docker Service Ollama läuft. Die Ergebnisse werden als GZIP komprimierte JSON mit dem Format ``YYYY-MM-DD_<GMT RUN ID>_answers_eval.json.gz`` gespeichert.

**(REMOTE)** Das Skript [ragas_eval_remote.py](scripts/ragas_eval_remote.py) verwendet das Framework RAGAS, um die Antworten der RAG App aus ``YYYY-MM-DD_<GMT RUN ID>_answers.json`` zu evaluieren. Der Judge ist eine OpenAI LLM, die über die API und den OPEN_API_KEY angesteuert wird. Die Ergebnisse werden als GZIP komprimierte JSON mit dem Format ``YYYY-MM-DD_<GMT RUN ID>_answers_eval.json.gz`` gespeichert.

**LOKAL:**
````shell
usage: ragas_evaluation.py [-h] -i INPUT

Evaluation der RAG Antworten mit RAGAS.

options:
  -h, --help         show this help message and exit
  -i, --input INPUT  Pfad zu *_answers.json.
````

**REMOTE:**
````shell
usage: ragas_eval_remote.py [-h] -i INPUT -k OPENAI_API_KEY

RAGAS Evaluation via OpenAI API.

options:
  -h, --help                            show this help message and exit
  -i, --input INPUT                     Pfad zu *_answers.json.
  -k, --openai-api-key OPENAI_API_KEY   OpenAI API Key.
````

Das Schema der gespeicherten JSON sieht so aus:
````json
{
  "meta": {
    "run_id": "<GMT RUN ID>",
    "run_date": "YYYY-MM-DD",
    "created_at": "Datum der Erstellung",
    "input_file": "Antwort JSON generiert mit get_gmt_answers.py",
    "judge": {
      "base_url": "URL zu lokal gehosteten LLM (über Ollama)",
      "model": "Name der (instruct) LLM"
    },
    "embedding_model": "Name des Embedding Modells",
    "metrics": [ 
      "faithfulness", 
      "answer_relevancy", 
      "context_utilization" 
    ]
  },
  "summary": {
    "faithfulness_mean": 0.1010101010101010,
    "answer_relevancy_mean": 0.0101010101010101,
    "context_utilization_mean": 0.6767676767676767,
    "n": 200
  },
  "records": [
    {
      "q_id": q_id von questions.json,
      "question": "question von questions.json",
      "answer": "Antwort der LLM",
      "context_meta": [
        {
          "source": "Dokumentenpfad von context_1",
          "chunk_index": Chunk Nummer von context_1,
          "type": "Dokumententyp von context_1"
        },
        "..."
      ],
      "metrics": {
        "faithfulness": 1.0,
        "answer_relevancy": 0.0,
        "context_utilization": 0.5
      }
    }, 
    "..."
  ]
}
````

### Messläufe zusammenfassen
Das Skript [create_ragas_summary.py](scripts/create_ragas_summary.py) erstellt eine statistische Auswertung von mehreren RAGAS Messläufen.

````shell
usage: create_ragas_summary.py [-h] -i INPUT_DIR [-o OUTPUT_NAME]

Aggregiert mehrere RAGAS *_eval.json(.gz) pro q_id über Runs.

options:
  -h, --help                      show this help message and exit
  -i, --input-dir INPUT_DIR       Ordner mit *_eval.json oder *_eval.json.gz Dateien.
  -o, --output-name OUTPUT_NAME   Ausgabename ohne Endung (.json.gz wird angehaengt).
````