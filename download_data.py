"""Downloads the three dataset files into the data/ folder.
Run once:  python download_data.py
"""
from pathlib import Path
import urllib.request

BASE = "https://raw.githubusercontent.com/Vonter/india-aviation-traffic/main/aggregated/"
FILES = {
    "city.csv": "domestic/city.csv",        # traffic between city pairs
    "carrier.csv": "domestic/carrier.csv",  # traffic by airline
    "daily.csv": "daily.csv",               # daily reports incl. on-time performance
}

data_dir = Path(__file__).parent / "data"
data_dir.mkdir(exist_ok=True)

for local_name, remote_path in FILES.items():
    print("Downloading", local_name, "...")
    urllib.request.urlretrieve(BASE + remote_path, data_dir / local_name)

print("Done! Files are in the data/ folder.")
