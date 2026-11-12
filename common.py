import os, json, re, logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("agent")

BASE = Path(__file__).parent
DATA = BASE / "data"
OUT = DATA / "output"
DATA.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)
STATE_FILE = DATA / "state.json"


def env(key, default=None):
    return os.getenv(key, default)


CLAUDE_MODEL = env("CLAUDE_MODEL", "claude-sonnet-5-5")


# ---------- tiny JSON state (pending approvals, already-covered topics) ----------
def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"pending": {}, "covered": []}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- Claude helper ----------
_client = None


def ask_json(system: str, user: str, max_tokens: int = 8000) -> dict:
    """Call Claude and return parsed JSON. Retries once if the JSON is malformed."""
    global _client
    import anthropic
    _client = _client or anthropic.Anthropic()
    last_err = None
    for _ in range(2):
        r = _client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in r.content if b.type == "text").strip()
        m = re.search(r"\{.*\}", text, re.S)
        try:
            return json.loads(m.group(0))
        except Exception as e:  # noqa
            last_err = e
            user += "\n\nYour last reply was not valid JSON. Reply with ONLY one valid JSON object."
    raise RuntimeError(f"Claude returned invalid JSON: {last_err}")
