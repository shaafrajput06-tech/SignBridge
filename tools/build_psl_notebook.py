"""Write notebooks/train_psl_v3.ipynb: the Stage 2 training run for Google Colab (free), as a fallback for
.github/workflows/psl-train.yml. It runs exactly the same commands, so the numbers are comparable.

    python tools/build_psl_notebook.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks" / "train_psl_v3.ipynb"
SITE = json.loads((ROOT / "shared_data" / "site.json").read_text(encoding="utf-8"))

CELLS = [
    ("markdown", """# SignBridge PSL model (master-v3 Stage 2)

Normally GitHub trains this model by itself (workflow *PSL model (Stage 2)*); you never need this notebook.
It exists in case GitHub's computers are too slow one day. It runs the very same commands.

**How to run** (`docs/HOW_TO_RUN_THE_NOTEBOOK.md`): open it in Google Colab, then *Runtime → Run all*.
About 30-60 minutes. At the end, download `psl-bundle.zip` from the Files panel (left).

It downloads only the licensed SignSpeak dataset (Apache-2.0) after checking SignBridge's licence ledger,
and saves no video: the dataset is hand landmarks only."""),
    ("code", f"""# 1. Get SignBridge (expected: "Cloning into 'SignBridge'..." and no error)
!git clone --depth 1 --branch v3/master https://github.com/{SITE['old_repositories'][0]}.git SignBridge
%cd SignBridge"""),
    ("code", """# 2. Install (expected: ends with "Successfully installed ..." or "Requirement already satisfied")
!pip -q install numpy PyYAML jsonschema "tensorflow-cpu>=2.16,<3" ai-edge-litert"""),
    ("code", """# 3. Export check with an untrained model (expected last line: "smoke check passed")
!python -m tools.psl_train.smoke"""),
    ("code", """# 4. Download and convert SignSpeak (expected: a block between ===SIGNSPEAK-SUMMARY-BEGIN=== and ...-END===)
!python -m tools.psl_data.signspeak --out data/psl-signspeak-words"""),
    ("code", """# 5. Train, measure and export (expected: the report between ===PSL-REPORT-BEGIN=== and ...-END===)
!python -m tools.psl_train --data data/psl-signspeak-words/signspeak.npz --out out/psl --epochs 100"""),
    ("code", """# 6. Pack the bundle for download (expected: "psl-bundle.zip ready")
!cd out && zip -qr ../psl-bundle.zip psl && cd .. && echo "psl-bundle.zip ready" """),
]


def build() -> dict:
    cells = []
    for kind, text in CELLS:
        cell = {"cell_type": kind, "metadata": {}, "source": text.splitlines(keepends=True)}
        if kind == "code":
            cell.update(execution_count=None, outputs=[])
        cells.append(cell)
    return {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                         "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


if __name__ == "__main__":
    OUT.write_text(json.dumps(build(), indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
