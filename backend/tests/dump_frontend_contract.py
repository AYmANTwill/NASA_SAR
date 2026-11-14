"""Writes every /api response (frontend adapter) as JSON files, on synthetic data, so they can be validated
against the frontend's own zod schemas:

    python tests/dump_frontend_contract.py <out_dir>
    npx tsx validate.ts <out_dir>        (validate.ts + contract.ts from the frontend repo, see tools/)

File names start with the schema name: answer__, step__, error__, discoveries__, watch__, watches__,
notifications__, library__, demo__, health__."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "contract_dump")
OUT.mkdir(parents=True, exist_ok=True)
tmp = Path(tempfile.mkdtemp(prefix="nisar_contract_"))
os.environ.update(NISAR_DATA=str(tmp / "data"), NISAR_CACHE=str(tmp / "cache"), NISAR_OFFLINE="1")
if len(sys.argv) > 2:
    os.environ["NISAR_DISCOVERIES_MODE"] = sys.argv[2]
subprocess.run([sys.executable, str(ROOT / "tests" / "make_synthetic.py"), str(tmp / "data")], check=True,
               capture_output=True)
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402

c = TestClient(api.app)
n = 0


def dump(kind, name, data):
    global n
    (OUT / f"{kind}__{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    n += 1


def ask(name, body):
    r = c.post("/api/ask", json=body)
    assert r.headers["content-type"].startswith("text/event-stream"), r.headers
    ans = None
    for i, block in enumerate(r.text.strip().split("\n\n")):
        lines = dict(line.split(": ", 1) for line in block.split("\n") if ": " in line)
        ev, data = lines.get("event"), json.loads(lines["data"])
        dump(ev, f"{name}_{i:02d}", data)
        if ev == "answer":
            ans = data
    return ans


answers = {
    "panama": ask("panama", {"question": "Où le sol a-t-il bougé après le séisme du 9 octobre 2026 au Panama ?",
                             "lang": "fr", "location": {"lat": 7.59, "lon": -80.77}}),
    "wahda": ask("wahda", {"question": "Le barrage Al Wahda se déforme-t-il depuis juin ?", "lang": "fr",
                           "location": None}),
    "soil_ar": ask("soil_ar", {"question": "ما رطوبة التربة في الغرب؟", "lang": "ar",
                               "location": {"lat": 34.5, "lon": -6.0}}),
    "surface_en": ask("surface_en", {"question": "Did the surface change after the Panama earthquake?", "lang": "en",
                                     "location": {"lat": 7.59 + 1 / 111, "lon": -80.77 + 1 / 110}}),
    "flood": ask("flood", {"question": "Mes champs ont-ils été inondés ?", "lang": "fr",
                           "location": {"lat": 34.5, "lon": -6.0 - 3 / 92}}),
}
ask("cached_again", {"question": "Le barrage Al Wahda se déforme-t-il depuis juin ?", "lang": "fr", "location": None})
ask("no_location", {"question": "Le barrage bouge-t-il ?", "lang": "fr", "location": None})
ask("unclear", {"question": "Bonjour", "lang": "fr", "location": {"lat": 34.5, "lon": -6.0}})

for k, a in answers.items():
    if a:
        r = c.get(f"/api/answers/{a['id']}")
        dump("answer" if r.status_code == 200 else "error", f"get_{k}", r.json())
r = c.get("/api/answers/does-not-exist")
dump("error", "answer_404", r.json())

dump("library", "all", c.get("/api/library").json())
dump("demo", "bundle", c.get("/api/demo").json())
for e in c.get("/api/demo").json()["entries"]:
    dump("answer", f"event_{e['answer_id']}", c.get(f"/api/answers/{e['answer_id']}").json())
r = c.get("/api/discoveries?region=MA")
dump("discoveries" if r.status_code == 200 else "error", "ma", r.json())
dump("error", "lband", c.get("/api/proofs/lband-vs-cband").json())

w = c.post("/api/watches", json={"answer_id": answers["wahda"]["id"]})
dump("watch", "created", w.json())
dump("watch", "created_again", c.post("/api/watches", json={"answer_id": answers["wahda"]["id"]}).json())
w2 = c.post("/api/watches", json={"answer_id": answers["panama"]["id"]}).json()
c.post(f"/api/watches/{w2['id']}/simulate?level=red")
c.post("/api/watches/check")
dump("watches", "list", c.get("/api/watches").json())
dump("notifications", "list", c.get("/api/notifications").json())
assert c.delete(f"/api/watches/{w.json()['id']}").status_code == 204
dump("watches", "after_delete", c.get("/api/watches").json())
dump("health", "ok", c.get("/api/health").json())
png = answers["panama"]["layers"][0]["url"]
assert c.get(png).status_code == 200 and c.get(png).headers["content-type"] == "image/png", png
print(f"{n} responses written to {OUT}")
