import argparse
import json
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

ORIGIN = "https://metrics.green-coding.io"
MEASUREMENTS_URL = "https://api.green-coding.io/v1/measurements/single/{id}"
PHASE_URL = "https://api.green-coding.io/v2/run/{id}"
OUT_DIR = Path("gmt-data/raw-data")


def fetch_json(url: str, key: str, timeout_s: int) -> dict:
    try:
        req = Request(
            url,
            headers={
                "Origin": ORIGIN,
                "X-Authentication": key,
                "Accept": "application/json",
            },
            method="GET",
        )

        with urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read()

        return json.loads(raw.decode("utf-8"))

    except Exception as e:
        raise RuntimeError(f"Response is not valid JSON for {url}") from e


def main() -> None:
    ap = argparse.ArgumentParser(description="Rufe die GMT API auf und speichere die Daten.")
    ap.add_argument("-k", "--key", required=True, help="X-Authentication token")
    ap.add_argument("-r", "--run-id", required=True, help="Messlauf-ID (UUID)")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    meas_path = OUT_DIR / f"{today}_{args.run_id}_measurements.json"
    phase_path = OUT_DIR / f"{today}_{args.run_id}_phase-data.json"

    # 1) GET measurements
    meas_url = MEASUREMENTS_URL.format(id=args.run_id)
    measurements = fetch_json(meas_url, args.key, timeout_s=600)
    meas_path.write_text(json.dumps(measurements, ensure_ascii=False), encoding="utf-8")
    print(f"Measurements gespeichert: {meas_path}")

    # 2) GET phase-data
    phase_url = PHASE_URL.format(id=args.run_id)
    phase_data = fetch_json(phase_url, args.key, timeout_s=120)
    phase_path.write_text(json.dumps(phase_data, ensure_ascii=False), encoding="utf-8")
    print(f"Phase-data gespeichert: {phase_path}\n########## DOWNLOAD DONE ##########")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e)
        raise SystemExit(1)
