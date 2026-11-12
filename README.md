# Telugu AI Channel Agent (faceless, AI images, you approve every video)

Two content lanes, every day:

| Lane | Sources | Style |
|---|---|---|
| 📰 **News** (default 2/day, ~4 min) | Google News (Telugu + English), Google Trends | Neutral news explainer for Telugu people worldwide |
| 🧠 **Explainer** (default 3/day, ~8 min) | Wikipedia most-read + On-this-day, Reddit, Hacker News, NASA, ScienceDaily, Ars Technica, Google Trends | Detailed storytelling in the style of Telugu facts / deep-thinking channels: science, space, history, mysteries, tech, geopolitics, biography, psychology/mindset |

Pipeline: collect -> pick topics -> gather source text (Wikipedia is the backbone for explainers) -> Telugu script ->
fact-check (+1 rewrite) -> Telugu voice -> **AI image per scene** + slow zoom -> AI thumbnail ->
**sent to your Telegram with Approve / Reject** -> upload only after you tap Approve.

## Quick setup (recommended)
    python setup_wizard.py
It installs packages, downloads the Telugu font, asks for your keys (hidden, tested, saved only to a local .env),
finds your Telegram chat id automatically, and guides the YouTube login. The manual steps below are the same thing by hand.

## Manual setup
1. `sudo apt install ffmpeg libraqm0 libfribidi0 libharfbuzz0b` (macOS: `brew install ffmpeg libraqm`). Windows: use WSL.
2. `pip install -r requirements.txt`
3. Download **Noto Sans Telugu Bold** (fonts.google.com) next to `main.py`.
4. `cp .env.example .env`, fill in: Anthropic key, Telegram bot token + chat id, image provider key (Gemini or OpenAI).
5. YouTube: Google Cloud project -> enable YouTube Data API v3 -> OAuth Desktop client -> save `client_secret.json` -> `python main.py auth`.
6. Test step by step:
   - `python main.py sources`  (are the feeds working?)
   - `python main.py dry 2`    (prints Telugu scripts only - read them)
   - `python main.py bot`, then message your bot `/runnow`
7. Deploy on a small VPS (systemd/Docker) so the 7:00 run happens by itself.

## Rules built in
- Scripts may use ONLY the gathered sources; a second AI pass fact-checks; thin-source topics are skipped, not guessed.
- Mysteries/theories are labelled as theories. No invented quotes or anecdotes.
- AI images never depict real people; news visuals are symbolic; every frame carries a small "AI illustration" tag.
- YouTube "altered/synthetic content" flag is set on upload; sources are listed in the description.

## Costs to watch
Each video uses ~1 AI image per ~20 seconds of narration. Check your image provider's per-image price and tune
`NEWS_VIDEOS`, `EXPLAINER_VIDEOS`, `*_MINUTES` in `.env` to fit your budget.

## Push to GitHub
    cd telugu_news_agent
    git init && git add . && git commit -m "Telugu AI channel agent"
    git branch -M main
    git remote add origin https://github.com/venkata-1/AI-Agent.git
    git push -u origin main
(.gitignore already keeps your keys, tokens and generated videos out of the repo.)
