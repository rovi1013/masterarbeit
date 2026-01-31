# Green Metrics Tool (GMT)

Das Green Metrics Tool ist eine modulare Suite aus verschiedenen Tools, die Energie- und CO₂-Daten für unterschiedliche Phasen des Softwarelebenszyklus erfassen.

## Referenzen
[**Green Metrics Tool Dokumentation**](https://docs.green-coding.io/)

[**Green Coding Solutions GmbH**](https://www.green-coding.io/)

## Struktur
````text
eval-gmt/
├── gmt-data/                           # MESSLAUF DATEN
│   ├── filtered-data/                  # Gefilterete Daten
│   └── raw_data/                       # Roh-Daten von GMT
│
├── scripts/                            # MESSDATEN AUFBEREITUNG
│   ├── create_measurement_summary.py   # Zusammenfassung eines Messlaufs
│   ├── filter_gmt_meassurement.py      # Filter der Messwerte
│   └── get_gmt_measurement.py          # Download der Messwerte
│
├── requirements.txt
└── README.md
````

## Workflow
1. Prerequisites
2. Messung auf GMT Testsystem durchführen
3. Ergebnisse von GMT API abrufen
4. Ergebnisse der Messung zusammenfassen

### Prerequisites
Setup des Python VENV und installation der Python Packages:
````shell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
````

### Messung auf GMT Testsystem durchführen
_Messungen mit Community Version haben einige Limitationen, siehe [GMT Website](https://www.green-coding.io/products/green-metrics-tool/)_. 

Die Messung kann über den Tab [Submit Software](https://metrics.green-coding.io/request.html) im Scenario Runner gestartet werden. Die Ergebnisse der Messung können unter [Runs / Repos](https://metrics.green-coding.io/runs.html) aufgerufen werden. Über die URL der einzelnen Messungen erhält man die ``GMT RUN ID``:  ``https://.../stats.html?id=<GMT RUN ID>``.

### Ergebnisse von GMT API abrufen
Das Skript [get_gmt_measurement.py](#downlaod-der-messungen) ruft 2 Endpoints der GMT API auf und speichert die Antworten als JSON mit den Formaten ``YYYY-MM-DD_<GMT RUN ID>_measurements.json`` und ``YYYY-MM-DD_<GMT RUN ID>_phase-data.json`` in [gmt-data/raw-data/](gmt-data/raw-data).
````shell
python .\scripts\get_gmt_measurement.py --key "<GMT AUTHENTICATION TOKEN>" --run-id "<GMT RUN ID>"
````

### Ergebnisse der Messung zusammenfassen
Die 2 Endpoints der GMT API geben eine Menge Raw Data zurück, diese Daten werden mit dem Skript [create_measurement_summary.py](#summary-der-messwerte) zusammengefasst und als GZIP komprimierte JSON mit dem Format ``YYYY-MM-DD_<GMT RUN ID>_summary.json.gz`` in [gmt-data/processed-data/](gmt-data/processed-data) abgespeichert.
````shell
python .\scripts\create_measurement_summary.py --measurements "*_measurements.json" --phase-data "*_phase-data.json"
````


## GMT Messwerte
GMT stellt eine Reihe von Messdaten zur Verfügung, in der Tabelle steht eine knappe Zusammenfassung der verfügbaren Metriken. Die Messwerte haben per Default alle eine ``sampling_rate`` von 99, was bedeutet, dass sie alle 99ms erhoben werden, also etwa 10 Messungen pro Sekunde. 

| Metric Provider                    | Beschreibung                                                           | Einheit |
|:-----------------------------------|:-----------------------------------------------------------------------|:--------|
| psu_energy_ac_mcp_machine_provider | Der Stromverrbauch des Gesamtsystems.<br>Gemessen vom MCP39F511N Chip. | mW      |
| network_io_cgroup_container        | Gesendete und empfangene Daten eines Containers.                       | Bytes   |
| cpu_energy_rapl_msr_component      | Energieverbrauch der CPU erhoben via RAPL.                             | 1e-6 J  |
| lmsensors_temperature_component    | Temperatur der CPU.                                                    | 1/100°C |
| cpu_utilization_procfs_system      | CPU Auslastung des Gesamtsystems.                                      | %       |
| cpu_utilization_cgroup_container   | CPU Auslastung einzelner Container.                                    | %       |
| memory_energy_rapl_msr_component   | Energieverbrauch des RAM erhoben via RAPL.                             | 1e-6 J  |
| memory_used_cgroup_container       | RAM Auslastung eines Containers.                                       | Bytes   |
| gpu_energy_nvidia_nvml_component   | Energieverbrauch durch die GPU erhoben via NVML                        | mW      |


## Skripts

### Downlaod der Messungen
Das Skript [get_gmt_measurement.py](scripts/get_gmt_measurement.py) läd die Messdaten über die [GMT API](https://api.green-coding.io/docs#/) herunter. Dafür sind der Authetication Token und die Messlauf-ID notwendig. Die Messdaten werden von ``/v1/measurements/single/{id}`` heruntergeladen und als JSON abgespeichert mit dem Namensformat ``YYYY-MM-DD_<GMT RUN ID>_measurements.json``. Die Datei ist so strukturiert:
````json
{
  "success": "[true/false]",
  "data": [
    [
      "Entity_Name",
      timestamp,
      "Messinterface_Name",
      value,
      "Einheit"
    ],
    ...
  ]
}
````
Das resultiert in einer mehrere Hunderttausend bis Millionen Zeilen langen JSON Datei, wobei die "data" Liste alle Messwerte beinhaltet und nicht weiter strukturiert ist. Daher ist eine weitere Datei für die Auswertung eines Messlaufs notwendig. Die Metadaten eines Messlaufs werdem über ``/v2/run/{id}`` heruntergeladen und als JSON abgespeichert mit dem Namensformat ``YYYY-MM-DD_<GMT RUN ID>_phase-data.json``.

````shell
usage: get_gmt_measurement.py [-h] -k KEY -r RUN_ID

Rufe die GMT API auf und speichere die Daten.

options:
  -h, --help           show this help message and exit
  -k, --key KEY        X-Authentication token
  -r, --run-id RUN_ID  Messlauf-ID (UUID)
````


### Summary der Messwerte
Das Skript [create_measurement_summary.py](scripts/create_measurement_summary.py) erstellt aus den beiden Dateien ``YYYY-MM-DD_<Messlauf-ID>_measurements.json`` und ``YYYY-MM-DD_<Messlauf-ID>_phase-data.json`` eine Zusammenfassung für den entsprechenden Messlauf.

````shell
usage: create_measurement_summary.py [-h] -m MEASUREMENTS -p PHASE_DATA [-c COMPRESS_LVL]

Fasse die Measurement und Phase-Data Daten zusammen.

options:
  -h, --help                            show this help message and exit
  -m, --measurements MEASUREMENTS       Pfad zu *_measurements.json
  -p, --phase-data PHASE_DATA           Pfad zu *_phase-data.json
  -c, --compress-lvl COMPRESS_LVL       Gzip compression level (1-9)
````

Das Schema der JSON Datei (Details zu einigen Teilen in den Tabellen):
````json
{
  "run": {
    "metadata": "Alles mögliche an Metadaten zu dem Messlauf aus *_phase-data.json; TABELLE"
  },
  "source_files": {
    "phase_data": "*_phase-data.json",
    "measurements": "*_measurements.json"
  },
  "windows": [
    {
      "name": "Name der GMT Messlauf-Window",
      "kind": "Typ der Window: gmt_phase|workflow_step|sub_window",
      "start_us": Start Timestamp in Mikrosekunden,
      "end_us": Ende Timestamp in Mikrosekunden,
      "duration_s": Dauer der Window
    },
    ...
  ],
  "records": [
    {
      "window": "Name der GMT Messlauf-Window",
      "kind": "Typ der Window: gmt_phase|workflow_step|sub_window",
      "metrics": {
        "Liste von Metriken pro Window aggregiert; TABELLEN": {
          "unit": "Unit",
          "enities": {
            "Entity_name_1": {
              "aggregation_type": Wert,
               ...
              "count": Anzahl der aggregierten Werte
            },
            "Entity_name_2": {
              ...
            }
          }
        }
      },
      ...
      "window_N": ...
    }
  ],
  "markers": {
    "Indexing": [
      "Auflistung aller Marker aus Indexing"
    ],
    "RAG Querries": [
      "Auflistung aller Marker aus RAG Querries"
    ]
  },
  "entity_mappings": {
    "entity_name_new": "entity_name_old aus *_measurements.json"
  },
  "stats": {
    "total_rows_seen": Anzahl der verarbeiteten JSON Reihen,
    "updates_written": Anzahl der verwendeten JSON Reihen
  },
  "notes": "Notizen"
}
````

In den meisten Fällen ist ``total_rows_seen`` detulich niedriger als ``updates_written``, da einige Reihen mehrfach verwendet werden. Beispielsweise die Werte aus der window ``[RUNTIME]`` kommen auch in den einzelnen windows des Typs ``workflow_step`` (Download Dataset, Indexing, Warmup Indexing, ...) vor.

Metadaten für Zusammenfassung des Messlaufs (aus *_phase-data.json):

| Name                     | Beschreibung                                 |
|:-------------------------|:---------------------------------------------|
| id                       | GMT Messlauf ID                              |
| name                     | GMT Messlauf Name                            |
| date                     | Datum des Messlaufs                          |
| uri                      | GitHub Repository Link                       |
| branch                   | GitHub Branch                                |
| commit_hash              | Hash des Git Commits                         |
| filename                 | Name der usage_scenario                      |
| machine_id               | ID der Testbench                             |
| gmt-hash                 | Hash des GMT Git Commit                      |
| created_at               | Erstellungs-Zeitpunkt des Messlaufs          |
| failed                   | Messlauf Erfolgreich durchlaufen (Boolean)   |
| warnings                 | Anzahl der Warnings in Messlauf              |
| start_measurement        | Start-Zeitpunkt des Messlaufs                |
| end_measurement          | End-Zeitpunkt des Messlaufs                  |
| usage_scenario_variables | Liste der verwendeten GMT Umgebungsvariablen |


Aggregation der einzelnen Metriken:

| Metric Provider                    | Unit  | Entities                                          | Aggregation | 
|:-----------------------------------|:------|:--------------------------------------------------|:------------|
| cpu_energy_rapl_msr_component      | uJ    | Package_0                                         | SUM Wh      |
| memory_energy_rapl_msr_component   | uJ    | DRAM_TOTAL                                        | SUM Wh      |
| gpu_energy_nvidia_nvml_component   | uJ    | GPU_TOTAL                                         | SUM Wh      |
| psu_energy_ac_mcp_machine_provider | uJ    | PSU_TOTAL                                         | SUM Wh      |
| cpu_utilization_procfs_system      | Ratio | [SYSTEM]                                          | MEAN/MAX    |
| cpu_utilization_cgroup_container   | Ratio | rag-app & ollama                                  | MEAN/MAX    |
| memory_used_cgroup_container       | Bytes | rag-app & ollama                                  | MEAN/MAX    |
| network_io_cgroup_container        | Bytes | rag-app & ollama                                  | SUM MiB/MAX |
| lmsensors_temperature_component    | C     | TEMP_CORE & TEMP_PACKAGE<br>unknown: TEMP_IGNORED | MEAN/MAX    |

Entity name mappings:

| Metric Provider                  | Entity Name GMT                | New Entity Name |
|:---------------------------------|:-------------------------------|:----------------|
| memory_energy_rapl_msr_component | DRAM_0                         | DRAM_TOTAL      |
| gpu_energy_nvidia_nvml_component | NVIDIA GeForce GTX 1080-0      | GPU_TOTAL       | 
| lmsensors_temperature_component  | coretemp-isa-0000_Core-0       | TEMP_CORE       |
| lmsensors_temperature_component  | coretemp-isa-0000_Package-id-0 | TEMP_PACKAGE    |
| lmsensors_temperature_component  | unknown                        | TEMP_IGNORED    |


### Filter der Messungen
Das Skript [filter_gmt_meassurement.py](scripts/filter_gmt_measurement.py) filtert bestimmte Messergebnisse aus den Roh-Messdaten ``YYYY-MM-DD_<Messlauf-ID>_measurements.json`` von GMT heraus. Außerdem wird die Datei zu einer ``.gz`` komprimiert. Der Output ist eine ``YYYY-MM-DD_<Messlauf-ID>_measurements_filtered.json.gz``. Insgesamt wird dadurch die Größe von ``>20MB`` der Roh-Messdaten auf ``<1MB`` reduziert. In der Tabelle sind die verwendeten Messwerte mit (✔) markiert und die herausgefilterten mit (✖).


| Metric Provider                    |   |
|:-----------------------------------|:--|
| psu_energy_ac_mcp_machine_provider | ✖ | 
| network_io_cgroup_container        | ✖ |
| cpu_energy_rapl_msr_component      | ✔ | 
| lmsensors_temperature_component    | ✖ |
| cpu_utilization_procfs_system      | ✔ |
| cpu_utilization_cgroup_container   | ✔ |
| memory_energy_rapl_msr_component   | ✔ |
| memory_used_cgroup_container       | ✔ |
| gpu_energy_nvidia_nvml_component   | ✔ |


````shell
usage: filter_gmt_measurement.py [-h] -i INPUT [-p]

Filtert bestimmte Metriken aus einem GMT Messlauf heraus.

options:
  -h, --help         show this help message and exit
  -i, --input INPUT  Input JSON Datei von GMT.
  -p, --plain        Output als plain .json (sonst komprimiert zu .json.gz).
````
