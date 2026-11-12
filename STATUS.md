# Project status / handoff notes (last updated 2026-11-12)

## Goal
Fully automated faceless Telugu YouTube channel for the global Telugu community. An AI agent collects topics daily,
writes Telugu scripts, generates voice + AI images, builds videos and sends each to the OWNER on Telegram.
Nothing is uploaded to YouTube until the owner taps Approve.

## What is built (all in this repo)
- `collect.py`   news lane (Google News RSS) + discovery lane (Wikipedia most-read/on-this-day, Reddit, HN, NASA, ScienceDaily, Ars) + Google Trends hints
- `writer.py`    topic pickers for 2 lanes, source gathering (Wikipedia as backbone for explainers), Telugu script writer, fact-check + 1 rewrite
- `imagegen.py`  AI images (Gemini or OpenAI), cache, Pexels fallback
- `media.py`     Telugu TTS (edge-tts free / Azure), parallel prep, Ken Burns video via ffmpeg, AI thumbnail, optional music
- `bot.py`       Telegram approval bot (Approve/Reject buttons, script file, sources, fact-check notes), daily scheduler, /runnow, /status
- `youtube.py`   OAuth + upload (AI-content disclosure flag, sources in description, thumbnail)
- `setup_wizard.py` one-command setup (installs, font, hidden key entry + tests, Telegram chat-id discovery)
- `main.py`      commands: bot | auth | sources | dry [N]

## Tested so far
- Code compiles; full video assembly tested OFFLINE with fake voice + plain background (ffmpeg zoom/concat, thumbnail, label).
- Font download link works; .env writer works.

## NOT yet tested with real services (do these first when resuming)
1. `python setup_wizard.py` end to end with real keys
2. `python main.py sources`  - do all feeds return items? (Reddit may block some IPs)
3. `python main.py dry 2`    - READ the Telugu scripts: naturalness, accuracy, neutrality
4. Telugu voice quality: compare te-IN-ShrutiNeural vs te-IN-MohanNeural, and edge vs azure
5. Gemini/OpenAI image model names (set in .env; they change often) and image look (tune IMAGE_STYLE)
6. Telugu text rendering on screen (needs libraqm) - check a thumbnail
7. Full run: send /runnow to the bot, approve one video, confirm YouTube upload (new API projects upload as private until Google audits)

## Open ideas / next steps
- Combined daily bulletin + Shorts clips from the best moments
- Burned-in Telugu subtitles; background music; intro/outro
- Cloud deployment (small VPS + Docker/systemd) so it runs without the owner's PC
- Tune script style after reviewing real output; add per-channel "voice" notes
- Track which topics perform on YouTube and feed that back into topic picking

## Owner decisions still open
- Daily mix (NEWS_VIDEOS / EXPLAINER_VIDEOS) and video lengths vs image cost
- Voice provider (edge for testing, azure for production)
- Whether to review politics/religion scripts more strictly before approving
