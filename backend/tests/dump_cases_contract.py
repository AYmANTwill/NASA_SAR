"""Writes the /api/cases responses as JSON files (cases__, case__, error__) next to dump_frontend_contract.py's output,
so validate.ts checks them with tools/frontend_contract/case_contract.ts:

    python tests/dump_cases_contract.py <out_dir>
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "contract_dump")
OUT.mkdir(parents=True, exist_ok=True)
tmp = Path(tempfile.mkdtemp(prefix="nisar_cases_"))
os.environ.update(NISAR_DATA=str(tmp / "data"), NISAR_CACHE=str(tmp / "cache"), NISAR_OFFLINE="1")
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402

c = TestClient(api.app)
n = 0


def dump(kind: str, name: str, data) -> None:
    global n
    (OUT / f"{kind}__{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    n += 1


r = c.get("/api/cases")
assert r.status_code == 200, r.text
summaries = r.json()
dump("cases", "list", summaries)
for s in summaries:
    r = c.get(f"/api/cases/{s['id']}")
    assert r.status_code == 200, (s["id"], r.text)
    dump("case", s["id"], r.json())
r = c.get("/api/cases/does-not-exist")
assert r.status_code == 404, r.text
dump("error", "case_404", r.json())
print(f"{n} case responses written to {OUT}")
