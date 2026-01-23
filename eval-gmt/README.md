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
│   └── raw_data/                       # Rod-Daten von GMT
│
├── scripts/                            # MESSDATEN AUFBEREITUNG
│   ├── create_measurement_summary.py   # Zusammenfassung eines Messlaufs
│   ├── filter_gmt_meassurement.py      # Filter der Messwerte
│   └── get_gmt_measurement.py          # Download der Messwerte
│
├── requirements.txt
└── README.md
````

## GMT Messwerte
Über die [GMT API](https://api.green-coding.io/docs#/) kann eine Reihe von Messdaten heruntergeladen werden (siehe [Download der Messungen](#downlaod-der-messungen)). In der Tabelle steht eine knappe Zusammenfassung der verfügbaren Metriken. Die Messwerte haben per Default alle eine ``sampling_rate`` von 99, was bedeutet, dass sie alle 99ms erhoben werden, also etwa 10 Messungen pro Sekunde. 

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

## GMT Mess-Durchläufe

| Datum      | Beschreibung     | ID                                   |
|:-----------|:-----------------|:-------------------------------------|
| 2026-01-15 | GMT Test Messung | eb96fce5-f8d5-442e-8edf-e66e8bdcc391 |
|            |                  |                                      |
|            |                  |                                      |
|            |                  |                                      |

## Skripts
Nutzung der Skripts in ``eval-gmt/`` (Windows):
````shell
# 1. Python virtual environment aufsetzen
python -m venv .venv
.venv/Scripts/activate

# 2. Python Packages installieren
pip install -r requirements.txt
````

### Downlaod der Messungen
Das Skript [get_gmt_measurement.py](scripts/get_gmt_measurement.py) läd die Messdaten über die [GMT API](https://api.green-coding.io/docs#/) herunter. Dafür sind der Authetication Token und die Messlauf-ID notwendig. Die Messdaten werden von ``/v1/measurements/single/{id}`` heruntergeladen und als JSON abgespeichert mit dem Namensformat ``JJJJ-MM-DD_<Messlauf-ID>_measurements.json``. Die Datei ist so strukturiert:
````json
{
  "success": [true/false],
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
Das resultiert in einer mehrere hunderttausend Zeilen langen JSON Datei, wobei die "data" Liste alle Messwerte beinhaltet und nicht weiter strukturiert ist. Daher ist eine weitere Datei für die Auswertung eines Messlaufs notwendig. Die Metadaten eines Messlaufs werdem über ``/v2/run/{id}`` heruntergeladen und als JSON abgespeichert mit dem Namensformat ``JJJJ-MM-DD_<Messlauf-ID>_phase-data.json``. Hier sind alle Informationen zum Messlauf gespeichert.

````shell
usage: get_gmt_measurement.py [-h] -k KEY -r RUN_ID

options:
  -h, --help           show this help message and exit
  -k, --key KEY        X-Authentication token
  -r, --run-id RUN_ID  Messlauf-ID (UUID)
````


### Summary der Messwerte
Das Skript [create_measurement_summary.py](scripts/create_measurement_summary.py) erstellt aus den beiden Dateien ``JJJJ-MM-DD_<Messlauf-ID>_measurements.json`` und ``JJJJ-MM-DD_<Messlauf-ID>_phase-data.json`` eine Zusammenfassung für den entsprechenden Messlauf.

````shell
usage: create_measurement_summary.py [-h] -m MEASUREMENTS -p PHASE_DATA [-c COMPRESS_LVL]

options:
  -h, --help                            show this help message and exit
  -m, --measurements MEASUREMENTS       Pfad zu *_measurements.json
  -p, --phase-data PHASE_DATA           Pfad zu *_phase-data.json
  -c, --compress-lvl COMPRESS_LVL       Gzip compression level (1-9)
````

**Regex für Markierungen in stdout**:
- ``.*``: beliebige Zeichen, beliebig viele
- ``##GMT_MARK##``: Markierung für timestamps in stdout
- ``\s+``: whitespace
- ``ts_us=(\d+)``: _ts_us_ gefolgt von einer Zahl (timestamp)
- ``\s+``: whitespace
- ``event=([A-Z0-9_]+)``: _event_ gefolgt von einem Namen der nur aus Großbustaben und Zahlen besteht
- ``\s+``: whitespace
- ``(?:\s+(.*))?$``: optionale Gruppe (``?``), fängt den restlichen String bis Zeilenende (``$``) ein


### Filter der Messungen
Das Skript [filter_gmt_meassurement.py](scripts/filter_gmt_measurement.py) filtert bestimmte Messergebnisse aus den Roh-Messdaten ``JJJJ-MM-DD_<Messlauf-ID>_measurements.json`` von GMT heraus. Außerdem wird die Datei zu einer ``.gz`` komprimiert. Der Output ist eine ``JJJJ-MM-DD_<Messlauf-ID>_measurements_filtered.json.gz``. Insgesamt wird dadurch die Größe von ``>20MB`` der Roh-Messdaten auf ``<1MB`` reduziert. In der Tabelle sind die verwendeten Messwerte mit (✔) markiert und die herausgefilterten mit (✖).


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

options:
  -h, --help         show this help message and exit
  -i, --input INPUT  Input JSON Datei von GMT.
  -p, --plain        Output als plain .json (sonst komprimiert zu .json.gz).
````
