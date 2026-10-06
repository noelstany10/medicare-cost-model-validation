#!/usr/bin/env bash
# Download CMS 2008-2010 DE-SynPUF Sample 1 (beneficiary summaries, inpatient, outpatient) into data/raw.
# Source page: https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-claims-synthetic-public-use-files/cms-2008-2010-data-entrepreneurs-synthetic-public-use-file-de-synpuf/de10-sample-1
set -euo pipefail
cd "$(dirname "$0")/.."
RAW=data/raw
mkdir -p "$RAW/zips"
rm -f "$RAW/.SYNTHETIC_TEST_DATA" "$RAW"/*.csv

UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
W=https://www.cms.gov/research-statistics-data-and-systems/downloadable-public-use-files/synpufs/downloads
D=https://downloads.cms.gov/files

# name | candidate URLs (tried in order)
declare -A URLS=(
  [bene_2008]="$W/de1_0_2008_beneficiary_summary_file_sample_1.zip $D/DE1_0_2008_Beneficiary_Summary_File_Sample_1.zip"
  [bene_2009]="$W/de1_0_2009_beneficiary_summary_file_sample_1.zip $D/DE1_0_2009_Beneficiary_Summary_File_Sample_1.zip"
  [bene_2010]="$W/de1_0_2010_beneficiary_summary_file_sample_1.zip $D/DE1_0_2010_Beneficiary_Summary_File_Sample_1.zip https://www.cms.gov/research-statistics-data-and-systems/statistics-trends-and-reports/synpufs/downloads/de1_0_2010_beneficiary_summary_file_sample_20.zip"
  [inpatient]="$W/de1_0_2008_to_2010_inpatient_claims_sample_1.zip $D/DE1_0_2008_to_2010_Inpatient_Claims_Sample_1.zip"
  [outpatient]="$W/de1_0_2008_to_2010_outpatient_claims_sample_1.zip $D/DE1_0_2008_to_2010_Outpatient_Claims_Sample_1.zip"
)

for name in bene_2008 bene_2009 bene_2010 inpatient outpatient; do
  ok=0
  for url in ${URLS[$name]}; do
    echo "-> $name: $url"
    if curl -fsSL --retry 4 --retry-delay 5 -A "$UA" -o "$RAW/zips/$name.zip" "$url" && unzip -tq "$RAW/zips/$name.zip" >/dev/null 2>&1; then
      ok=1; break
    fi
    echo "   failed, trying next mirror"
  done
  [ "$ok" = 1 ] || { echo "ERROR: could not download $name"; exit 1; }
  unzip -oq "$RAW/zips/$name.zip" -d "$RAW/zips/$name"
done

# Normalise extracted CSV names to the names expected by src/config.py
python3 - <<'EOF'
import glob, os, shutil
raw = "data/raw"
targets = {
    "bene_2008": "DE1_0_2008_Beneficiary_Summary_File_Sample_1.csv",
    "bene_2009": "DE1_0_2009_Beneficiary_Summary_File_Sample_1.csv",
    "bene_2010": "DE1_0_2010_Beneficiary_Summary_File_Sample_1.csv",
    "inpatient": "DE1_0_2008_to_2010_Inpatient_Claims_Sample_1.csv",
    "outpatient": "DE1_0_2008_to_2010_Outpatient_Claims_Sample_1.csv",
}
for k, t in targets.items():
    csvs = [p for p in glob.glob(f"{raw}/zips/{k}/**/*", recursive=True) if p.lower().endswith(".csv")]
    assert len(csvs) == 1, f"{k}: expected 1 csv, found {csvs}"
    shutil.move(csvs[0], f"{raw}/{t}")
    print(f"{t}: {os.path.getsize(f'{raw}/{t}')/1e6:.1f} MB")
shutil.rmtree(f"{raw}/zips")
EOF
echo "DE-SynPUF Sample 1 ready in $RAW"
