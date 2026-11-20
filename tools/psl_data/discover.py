"""Look inside the licensed PSL datasets before writing their converters (master-v3 Stage 2).

Lists every file of each dataset through the public APIs (Hugging Face, Mendeley Data), downloads the
smallest SignSpeak archive and prints its layout: member names, file types, and the shape and first
values of a few samples. Prints only; writes nothing to the repository. Every dataset listed here has a
ledger entry that allows training (data/LICENSES.yaml), checked before anything is downloaded.

    python -m tools.psl_data.discover
"""

from __future__ import annotations

import io
import json
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from data_engine.ledger import assert_allowed

UA = {"User-Agent": "SignBridge-psl-data/1.0 (https://github.com/shaafrajput06-tech/SignBridge)"}
SIGNSPEAK_HF = "mohibkhansherwani/DynamicWordLevelPakistanSignLanguageDataset"
MENDELEY = {  # ledger id -> (Mendeley dataset id, version)
    "psl-pkslmnm": ("m3m9924p3v", 2),
    "psl-ualpha40": ("3pvnnckxyb", 3),
    "psl-expression-hands": ("4d6tj5snkd", 3),
}


def get(url: str, timeout: int = 120) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as response:  # noqa: S310
        return response.read()


def show_array_like(name: str, data: bytes) -> None:
    suffix = Path(name).suffix.lower()
    try:
        if suffix == ".npy":
            import numpy as np

            array = np.load(io.BytesIO(data), allow_pickle=False)
            print(f"    {name}: npy shape {array.shape} dtype {array.dtype} first {array.reshape(-1)[:6]}")
        elif suffix in (".csv", ".txt"):
            lines = data.decode("utf-8", errors="replace").splitlines()
            print(f"    {name}: {len(lines)} lines; first: {lines[:3]}")
        elif suffix == ".json":
            obj = json.loads(data.decode("utf-8"))
            print(f"    {name}: json {type(obj).__name__} keys/len {list(obj)[:10] if isinstance(obj, dict) else len(obj)}")
        elif suffix in (".pkl", ".pickle"):
            print(f"    {name}: pickle ({len(data)} bytes) - not opened (pickles can run code)")
        else:
            print(f"    {name}: {len(data)} bytes")
    except Exception as error:  # noqa: BLE001
        print(f"    {name}: could not read ({error})")


def signspeak() -> None:
    assert_allowed("psl-signspeak-words", "train_labels")
    info = json.loads(get(f"https://huggingface.co/api/datasets/{SIGNSPEAK_HF}"))
    files = [s["rfilename"] for s in info.get("siblings", [])]
    print(f"SignSpeak (Hugging Face {SIGNSPEAK_HF}): sha {info.get('sha')}, licence {info.get('cardData', {}).get('license')}")
    for name in files:
        print("  file:", name)
    zips = [f for f in files if f.lower().endswith(".zip")]
    if not zips:
        return
    sizes = {}
    for name in zips:
        request = urllib.request.Request(f"https://huggingface.co/datasets/{SIGNSPEAK_HF}/resolve/main/{name}", headers=UA, method="HEAD")
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
            sizes[name] = int(response.headers.get("Content-Length") or 0)
    smallest = min(zips, key=lambda n: sizes[n] or 1 << 62)
    print(f"  downloading the smallest archive: {smallest} ({sizes[smallest]} bytes)")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "a.zip"
        path.write_bytes(get(f"https://huggingface.co/datasets/{SIGNSPEAK_HF}/resolve/main/{smallest}", timeout=900))
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            print(f"  {len(names)} members; first 25:")
            for name in names[:25]:
                print("   ", name)
            folders = sorted({n.split("/")[0] for n in names})[:10]
            second = sorted({"/".join(n.split("/")[:2]) for n in names if n.count("/") >= 1})[:15]
            print("  top folders:", folders)
            print("  second level:", second)
            suffixes = {}
            for n in names:
                suffixes[Path(n).suffix.lower()] = suffixes.get(Path(n).suffix.lower(), 0) + 1
            print("  file types:", suffixes)
            samples = [n for n in names if Path(n).suffix.lower() in (".npy", ".csv", ".json", ".txt")][:4]
            for n in samples:
                show_array_like(n, archive.read(n))


def mendeley(ledger_id: str, dataset: str, version: int) -> None:
    assert_allowed(ledger_id, "train_labels")
    url = f"https://data.mendeley.com/public-api/datasets/{dataset}/files?folder_id=root&version={version}"
    try:
        files = json.loads(get(url))
    except Exception as error:  # noqa: BLE001
        print(f"{ledger_id}: listing failed ({error})")
        return
    print(f"{ledger_id} (Mendeley {dataset} v{version}): {len(files)} entries at the top level")
    for item in files[:40]:
        details = item.get("content_details", {})
        print(f"  {item.get('filename')} | {details.get('size')} bytes | {details.get('content_type')} | folder={item.get('folder_id')}")


def main() -> None:
    try:
        signspeak()
    except Exception as error:  # noqa: BLE001
        print("SignSpeak discovery failed:", error)
    for ledger_id, (dataset, version) in MENDELEY.items():
        mendeley(ledger_id, dataset, version)


if __name__ == "__main__":
    main()
