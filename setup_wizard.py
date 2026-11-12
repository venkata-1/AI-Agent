"""One-command setup. Uses only the Python standard library so it can run before anything is installed.
Run:  python setup_wizard.py
Your keys are typed into YOUR terminal (hidden), tested, and saved to the local .env file only."""
import getpass, json, os, platform, re, shutil, subprocess, sys, time, urllib.request, urllib.error
from pathlib import Path

HERE = Path(__file__).parent
ENV = HERE / ".env"
FONT = HERE / "NotoSansTelugu.ttf"
FONT_URLS = [
    "https://github.com/google/fonts/raw/main/ofl/notosanstelugu/NotoSansTelugu%5Bwdth%2Cwght%5D.ttf",
    "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanstelugu/NotoSansTelugu%5Bwdth%2Cwght%5D.ttf",
]


def say(msg): print(msg, flush=True)
def ok(msg): say(f"  ✅ {msg}")
def bad(msg): say(f"  ❌ {msg}")


def http(url, headers=None, data=None, timeout=30):
    req = urllib.request.Request(url, headers=headers or {}, data=data)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ---------------------------------------------------------------- step 1: system tools
def check_system():
    say("\n[1/6] Checking your computer")
    if sys.version_info < (3, 10):
        bad(f"Python {sys.version_info.major}.{sys.version_info.minor} found; need 3.10+. Install from python.org")
        sys.exit(1)
    ok(f"Python {sys.version.split()[0]}")
    os_name = platform.system()
    hints = {"Linux": "sudo apt install ffmpeg libraqm0 libfribidi0 libharfbuzz0b",
             "Darwin": "brew install ffmpeg libraqm",
             "Windows": "Install ffmpeg (winget install ffmpeg). For correct Telugu text, run this project inside WSL/Ubuntu."}
    missing = [t for t in ("ffmpeg", "ffprobe") if not shutil.which(t)]
    if missing:
        bad(f"missing: {', '.join(missing)}.  Run:  {hints.get(os_name, 'install ffmpeg')}")
        say("     Then run this wizard again.")
        sys.exit(1)
    ok("ffmpeg found")


# ---------------------------------------------------------------- step 2: python packages
def install_packages():
    say("\n[2/6] Installing Python packages (1-3 minutes)")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", str(HERE / "requirements.txt")])
    if r.returncode != 0:
        bad("pip install failed - scroll up for the error (try a virtual environment: python -m venv venv)")
        sys.exit(1)
    ok("packages installed")
    try:
        from PIL import features
        ok("Telugu text engine (libraqm) available") if features.check("raqm") else bad(
            "libraqm missing - Telugu letters on screen may look broken. Install it (see README step 1).")
    except Exception:
        pass


# ---------------------------------------------------------------- step 3: font
def get_font():
    say("\n[3/6] Telugu font")
    if FONT.exists():
        ok("font already present")
        return
    for u in FONT_URLS:
        try:
            FONT.write_bytes(http(u, timeout=120))
            ok("downloaded Noto Sans Telugu")
            return
        except Exception as e:  # noqa
            last = e
    bad(f"could not download automatically ({last}). Download 'Noto Sans Telugu' from fonts.google.com, "
        f"save as {FONT.name} in this folder.")


# ---------------------------------------------------------------- step 4: keys
def ask_secret(label, how, required=True):
    say(f"\n  {label}\n    How to get it: {how}")
    while True:
        v = getpass.getpass("    Paste here (hidden, Enter to skip): ").strip() if not required else \
            getpass.getpass("    Paste here (hidden): ").strip()
        if v or not required:
            return v


def test_anthropic(k):
    http("https://api.anthropic.com/v1/models", {"x-api-key": k, "anthropic-version": "2023-06-01"})


def test_telegram(k):
    d = json.loads(http(f"https://api.telegram.org/bot{k}/getMe"))
    return d["result"]["username"]


def test_gemini(k):
    http(f"https://generativelanguage.googleapis.com/v1beta/models?key={k}")


def test_openai(k):
    http("https://api.openai.com/v1/models", {"Authorization": f"Bearer {k}"})


def test_pexels(k):
    http("https://api.pexels.com/v1/search?query=test&per_page=1", {"Authorization": k})


def collect_keys():
    say("\n[4/6] API keys (typed hidden; saved only in the local .env file)")
    vals = {}

    def verified(name, label, how, tester, required=True):
        while True:
            v = ask_secret(label, how, required)
            if not v:
                return ""
            try:
                extra = tester(v)
                ok(f"{name} works" + (f" (bot @{extra})" if extra else ""))
                return v
            except Exception as e:  # noqa
                bad(f"{name} test failed: {e}. Check the key and try again.")

    vals["ANTHROPIC_API_KEY"] = verified("Anthropic", "ANTHROPIC key (writes the scripts)",
                                         "console.anthropic.com -> API Keys -> Create key", test_anthropic)
    vals["TELEGRAM_BOT_TOKEN"] = verified("Telegram", "TELEGRAM BOT token (sends you videos to approve)",
                                          "In Telegram, chat with @BotFather -> /newbot -> copy the token", test_telegram)
    say("\n  Image generator for the AI pictures:")
    choice = input("    Type 1 = Gemini (Google AI Studio key), 2 = OpenAI, 3 = none (stock photos only) [1]: ").strip() or "1"
    if choice == "1":
        vals["IMAGE_PROVIDER"] = "gemini"
        vals["GEMINI_API_KEY"] = verified("Gemini", "GEMINI key", "aistudio.google.com -> Get API key", test_gemini)
    elif choice == "2":
        vals["IMAGE_PROVIDER"] = "openai"
        vals["OPENAI_API_KEY"] = verified("OpenAI", "OPENAI key", "platform.openai.com -> API keys", test_openai)
    else:
        vals["IMAGE_PROVIDER"] = "none"
    p = verified("Pexels", "PEXELS key (OPTIONAL stock-photo backup, free)", "pexels.com/api -> request key",
                 test_pexels, required=False)
    if p:
        vals["PEXELS_API_KEY"] = p
    name = input("\n  Your YouTube channel name (shown on videos): ").strip()
    if name:
        vals["CHANNEL_NAME"] = name
    return vals


# ---------------------------------------------------------------- step 5: telegram chat id
def find_chat_id(token):
    say("\n[5/6] Linking Telegram")
    say("  Open Telegram, find YOUR new bot, press START and send it the word:  hi")
    say("  Waiting up to 2 minutes...")
    end = time.time() + 120
    while time.time() < end:
        try:
            d = json.loads(http(f"https://api.telegram.org/bot{token}/getUpdates", timeout=15))
            for u in reversed(d.get("result", [])):
                msg = u.get("message") or {}
                if msg.get("chat", {}).get("id"):
                    cid = str(msg["chat"]["id"])
                    ok(f"found your chat (id {cid}); only this chat can approve videos")
                    return cid
        except Exception:
            pass
        time.sleep(3)
    bad("no message received. Message @userinfobot to get your id, then put it in .env as OWNER_CHAT_ID")
    return ""


# ---------------------------------------------------------------- write .env
def write_env(vals):
    src = ENV if ENV.exists() else HERE / ".env.example"
    text = src.read_text(encoding="utf-8")
    for k, v in vals.items():
        if re.search(rf"^{k}=.*$", text, re.M):
            text = re.sub(rf"^{k}=.*$", lambda m: f"{k}={v}", text, flags=re.M)
        else:
            text += f"\n{k}={v}"
    ENV.write_text(text, encoding="utf-8")
    try:
        os.chmod(ENV, 0o600)
    except Exception:
        pass


# ---------------------------------------------------------------- step 6: youtube
def youtube_step():
    say("\n[6/6] YouTube upload permission")
    if (HERE / "token.json").exists():
        ok("already authorised")
        return
    if not (HERE / "client_secret.json").exists():
        say("  Not done yet. You need ONE file from Google (5 minutes, free):")
        say("   1. console.cloud.google.com -> create project -> APIs & Services -> Library -> enable 'YouTube Data API v3'")
        say("   2. OAuth consent screen -> External -> add yourself as a Test user")
        say("   3. Credentials -> Create credentials -> OAuth client ID -> Desktop app -> Download JSON")
        say("   4. Save it in this folder as  client_secret.json , then run:  python setup_wizard.py")
        return
    if input("  client_secret.json found. Open the browser to log in to YouTube now? [Y/n] ").strip().lower() != "n":
        subprocess.run([sys.executable, str(HERE / "main.py"), "auth"])


def main():
    say("=== Telugu AI Channel Agent - setup wizard ===")
    check_system()
    install_packages()
    get_font()
    vals = {}
    if ENV.exists() and input("\n.env already exists. Re-enter keys? [y/N] ").strip().lower() != "y":
        say("[4/6] keeping existing keys")
    else:
        vals = collect_keys()
        vals["FONT_PATH"] = "./" + FONT.name
        if vals.get("TELEGRAM_BOT_TOKEN"):
            cid = find_chat_id(vals["TELEGRAM_BOT_TOKEN"])
            if cid:
                vals["OWNER_CHAT_ID"] = cid
        write_env(vals)
        ok("saved .env")
    youtube_step()
    say("\nDone. Next:")
    say("  python main.py sources     # check the news/discovery feeds")
    say("  python main.py dry 2       # read 2 Telugu scripts (cheap test)")
    say("  python main.py bot         # start the agent, then send /runnow to your bot")


if __name__ == "__main__":
    main()
