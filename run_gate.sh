#!/bin/bash
# Biography of a Breath — 4-hour data gate. Run from this folder in Terminal:  bash run_gate.sh
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
python gate/01_fetch_gfs.py
for city in "Delhi 28.6139 77.2090" "Chennai 13.0827 80.2707" "London 51.5074 -0.1278"; do
  set -- $city
  for lev in 10 850; do python gate/02_trajectory.py $1 $2 $3 $lev; done
  python gate/03_places.py out/journey_$1_10.json || echo "  (places step failed for $1 — continuing)"
  python gate/04_preview.py out/journey_$1_10.json
done
echo; echo "GATE DONE. Tell Claude 'gate done' — results are in out/."
