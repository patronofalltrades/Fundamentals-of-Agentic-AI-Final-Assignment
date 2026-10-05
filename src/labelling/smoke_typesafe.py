"""One live Jev call (2 demo reviews) via TypeSafe. Costs a fraction of a cent.

Run from the repo root:  python3 src/labelling/smoke_typesafe.py
Reads TYPESAFE_API_KEY from .env (git-ignored). Never prints the key.
"""
import io, json, os, re, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG = os.path.join(ROOT, "src", "labelling", "smoke_typesafe.log")
_log = open(LOG, "w")
_print = print
def print(*a, **k):  # noqa: A001  -- mirror output to the log (key is never printed)
    _print(*a, **k); _print(*a, file=_log, flush=True)
for line in open(os.path.join(ROOT, ".env")):
    m = re.match(r"\s*([A-Z_]+)\s*=\s*(.*?)\s*$", line)
    if m and not line.lstrip().startswith("#") and m.group(2):
        os.environ.setdefault(m.group(1), m.group(2).strip("\"'"))
if not os.environ.get("TYPESAFE_API_KEY"):
    print("TYPESAFE_API_KEY missing in .env"); sys.exit(1)
sys.path.insert(0, os.path.join(ROOT, "src"))
from labelling import model_client as mc  # noqa: E402

captured, _orig = {}, urllib.request.urlopen
class _Body(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): pass
def _spy(req, timeout=None):
    with _orig(req, timeout=timeout) as resp:
        captured["status"], captured["body"] = resp.status, resp.read()
    return _Body(captured["body"])
urllib.request.urlopen = _spy

client = mc.create_client({})
print("client:", type(client).__name__, client.model, client.endpoint)
reviews = [mc.ReviewInput("demo-1", "Keeps logging me out every day. I can't even open my playlists."),
           mc.ReviewInput("demo-2", "Love it! Best music app. Please bring back the old shuffle though.")]
try:
    res = client.classify_batch(reviews, "typesafe/jev-1.13.0:smoke")
except Exception as e:  # noqa: BLE001
    print("ERROR", type(e).__name__, str(e)[:800])
    if "body" in captured: print(captured["body"][:800])
    sys.exit(1)
raw = json.loads(captured["body"])
print("HTTP", captured["status"], "| served model:", raw.get("model"), "| id:", raw.get("id"), "| usage:", raw.get("usage"))
print("response keys:", list(raw))
print("sample raw answer:", json.dumps(raw["answers"].get("topic_demo-1"))[:400])
for r in res.records:
    print(json.dumps(r.__dict__, ensure_ascii=False))
print("OK")
_print(f"(saved to {LOG})")
