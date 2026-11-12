"""Steps 2-5: pick topics (two lanes), gather & verify sources, write Telugu script, fact-check it."""
import json
from common import ask_json, env, log
from collect import fetch_article, wiki_fetch

AUDIENCE = (
    "Telugu-speaking people living all over the world (USA, Gulf, UK, Australia, India). "
    "They love: Andhra/Telangana politics, Tollywood, temples & culture, visas/NRI life, cricket, business, "
    "and also curiosity content - science, space, history, mysteries, technology/AI, geopolitics explained, "
    "biographies, psychology and mindset - in the style of popular Telugu facts channels."
)


# ------------------------------------------------------------------ 2a. NEWS lane picker
def pick_stories(items, covered, n, trends):
    pool = [i for i in items if i["lane"] == "news"][:150]
    listing = "\n".join(f'{i["id"]} | {i["source"]} | {i["title"]}' for i in pool)
    system = "You are the news editor of a Telugu YouTube channel. Reply with ONLY a JSON object."
    user = f"""Audience: {AUDIENCE}

Google Trends right now (India/US searches): {json.dumps(trends[:25], ensure_ascii=False)}

Pick the {n} most important/interesting NEWS STORIES for this audience from the headlines below (id | source | title).
Group headlines that cover the same story. Rules:
- Category mix: politics (AP/Telangana + national), cinema, religion/culture, NRI/diaspora/visa, sports, business/tech, world. Never 2 from the same category unless n > 5.
- Prefer stories covered by 2+ different sources, and ones matching what people are searching.
- Skip: unverified rumours, gossip with no sourcing, graphic violence, anything that could incite communal hatred.
- Do NOT pick stories already covered: {json.dumps(covered[-80:], ensure_ascii=False)}

Return JSON:
{{"stories":[{{"topic_en":"short English label","category":"politics|cinema|religion|nri|sports|business|world|other","item_ids":[max 5 ids],"wiki_titles":["0-2 exact English Wikipedia article titles for background, or empty"],"why":"one line"}}]}}

HEADLINES:
{listing}"""
    return ask_json(system, user, 3000)["stories"][:n]


# ------------------------------------------------------------------ 2b. EXPLAINER lane picker
def pick_topics(items, covered, n, trends):
    pool = [i for i in items if i["lane"] == "discovery"][:160]
    listing = "\n".join(f'{i["id"]} | {i["source"]} | {i["title"]}' for i in pool)
    system = "You are the content strategist of a hugely popular Telugu facts/explainer YouTube channel. Reply with ONLY a JSON object."
    user = f"""Audience: {AUDIENCE}

Google Trends right now: {json.dumps(trends[:25], ensure_ascii=False)}

From the raw ideas below (id | source | title) choose {n} topics for DETAILED 8-minute explainer videos
in the style of Telugu channels like V R Facts (facts, science, history, mysteries, technology, geopolitics, biographies,
trending topics) and Think Deep (psychology, mindset, deep-thinking stories).
You may also propose topics of your own inspired by the list or by trends.

Choose for: a strong curiosity hook, real substance (enough to explain for 8 minutes), appeal to Telugu people worldwide.
Mix categories: {n} videos must come from DIFFERENT categories among: science, space, history, mystery, technology, geopolitics, economy, psychology, biography, health, india.
Avoid: pseudoscience, conspiracy theories presented as true, medical/financial advice, comparing religions, anything already covered:
{json.dumps(covered[-80:], ensure_ascii=False)}

IMPORTANT: every topic must be explainable from ENGLISH WIKIPEDIA articles, so give 1-3 exact existing Wikipedia article titles.

Return JSON:
{{"stories":[{{"topic_en":"specific working title","category":"science|space|history|mystery|technology|geopolitics|economy|psychology|biography|health|india","angle":"the curiosity angle in one line","item_ids":[related ids or empty],"wiki_titles":["Exact Wikipedia Title", "..."]}}]}}

IDEAS:
{listing}"""
    return ask_json(system, user, 3000)["stories"][:n]


# ------------------------------------------------------------------ 3. gather sources
def gather_sources(story, items, lane):
    by_id = {i["id"]: i for i in items}
    wiki_titles = list(story.get("wiki_titles") or [])
    sources = []
    for iid in (story.get("item_ids") or [])[:5]:
        it = by_id.get(iid)
        if not it:
            continue
        if it.get("wiki_title") and it["wiki_title"] not in wiki_titles:
            wiki_titles.append(it["wiki_title"])
        if it.get("link"):
            sources.append({"source": it["source"], "title": it["title"], "url": it["link"],
                            "text": fetch_article(it["link"], 6000)})
    wlimit = 14000 if lane == "explainer" else 5000
    for t in wiki_titles[:3]:
        w = wiki_fetch(t, wlimit)
        if w:
            sources.append({"source": "Wikipedia", "title": w[0], "url": w[1], "text": w[2]})
    story["distinct_sources"] = len({s["source"] for s in sources if len(s["text"]) > 200})
    story["confirmed"] = story["distinct_sources"] >= 2
    log.info("%s: %d usable sources", story["topic_en"], story["distinct_sources"])
    return sources


def _sources_block(sources):
    parts = []
    for n, s in enumerate(sources, 1):
        body = s["text"] or "(text unavailable - headline only)"
        parts.append(f'[S{n}] {s["source"]} | {s["title"]}\n{body}')
    return "\n\n".join(parts)


# ------------------------------------------------------------------ 4. script
BASE_RULES = """You are a senior Telugu scriptwriter and narrator for a YouTube channel serving Telugu people worldwide.

ABSOLUTE RULES
1. Use ONLY facts found in the provided SOURCES. Never add names, numbers, dates, quotes, anecdotes or dialogue from memory. NEVER invent quotes, conversations or "it is said that" stories. If the sources don't say it, don't say it.
2. Mysteries / unsolved questions / theories: say clearly they are theories or unproven ("శాస్త్రవేత్తలు ఇలా భావిస్తున్నారు…"). Never present speculation as fact.
3. Politics: strictly neutral; attribute claims to who made them; present both sides; no insults or loaded words.
4. Religion: respectful and factual; never compare or criticise faiths.
5. Never state accusations against named people as proven. No medical, legal or financial advice.
6. If the topic is only confirmed by one source, attribute carefully ("నివేదికల ప్రకారం…").

LANGUAGE: natural SPOKEN Telugu in a warm, confident professional narrator voice - not bookish or archaic, easy for a global audience.
Write numbers/dates the way a narrator would SAY them. Common English words used in everyday Telugu (వీసా, కోర్టు, రాకెట్) are fine. Keep proper nouns correct and consistent.

IMAGES: every segment needs an AI image prompt in English: one concrete, vivid scene (25-45 words), different composition each time
(wide shot, close-up, aerial, macro, silhouette, over-the-shoulder...). The image generator adds the art style itself.
- NO text, letters, logos or signs in the image.
- NEVER depict real, identifiable people (no celebrity/politician/historical-figure faces). Use symbolic scenes, objects, places, silhouettes or generic anonymous figures.
- For news about real events, use symbolic/illustrative imagery, never a realistic fake picture of the event itself.
"""

NEWS_STYLE = """FORMAT: news explainer, about {words} Telugu words, {segs} segments.
Structure: strong hook -> what happened -> background -> why it matters / what next / what it means for Telugu people abroad -> short neutral wrap-up."""

EXPLAINER_STYLE = """FORMAT: detailed storytelling explainer (like top Telugu facts channels), about {words} Telugu words, {segs} segments of ~55 words.
Structure:
1. HOOK (first 2 segments): open with the most surprising fact or question from the sources. Promise what the viewer will understand by the end.
2. BUILD: chapters that each reveal something new. Use "open loops" ("కానీ అసలు షాకింగ్ విషయం ఏమిటంటే…"), simple analogies a Telugu viewer relates to, and clear step-by-step explanation of HOW and WHY - go deep, not shallow.
3. MID-VIDEO RE-HOOK around the halfway point.
4. PAYOFF + key takeaway. For psychology/mindset topics: practical reflection grounded only in the sources, presented as ideas to think about.
5. Close: one line asking viewers to like and subscribe (ఈ వీడియో నచ్చితే సబ్‌స్క్రైబ్ చేయండి)."""

SCHEMA = """
Reply with ONLY this JSON:
{
 "title_te": "curiosity-driven but HONEST Telugu title, max 70 chars",
 "title_en": "English title for search",
 "description_te": "3-4 sentence Telugu description",
 "tags": ["10-14 tags, Telugu and English"],
 "thumbnail_text_te": "max 4 punchy Telugu words for the thumbnail",
 "thumbnail_prompt_en": "dramatic, eye-catching thumbnail scene, same image rules",
 "segments": [
   {"narration_te": "spoken text", "headline_te": "very short on-screen text, max 10 words", "image_prompt_en": "...", "image_query_en": "2-4 word generic stock-photo query"}
 ]
}"""


def write_script(story, sources, lane, feedback=None):
    minutes = int(env("EXPLAINER_MINUTES", "8")) if lane == "explainer" else int(env("NEWS_MINUTES", "4"))
    words = minutes * 120
    segs = max(6, words // 55)
    style = (EXPLAINER_STYLE if lane == "explainer" else NEWS_STYLE).format(words=words, segs=segs)
    user = f"""TOPIC: {story['topic_en']}  (category: {story['category']})
{('ANGLE: ' + story['angle']) if story.get('angle') else ''}
CONFIRMED BY 2+ INDEPENDENT SOURCES: {story['confirmed']}

SOURCES:
{_sources_block(sources)}
"""
    if feedback:
        user += f"\n\nA fact-checker found these problems in your previous draft. Fix ALL of them:\n{json.dumps(feedback, ensure_ascii=False)}"
    return ask_json(BASE_RULES + "\n" + style + "\n" + SCHEMA, user, 16000)


# ------------------------------------------------------------------ 5. fact-check
def fact_check(script, sources):
    system = "You are a strict fact-checker. Reply with ONLY a JSON object."
    narration = "\n".join(f"{i+1}. {s['narration_te']}" for i, s in enumerate(script["segments"]))
    user = f"""Check the Telugu script against the SOURCES. Flag any claim, name, number, date, quote, anecdote or implication NOT supported by the sources;
speculation presented as fact; one-sided/loaded political wording; accusations stated as proven fact; any invented quote or story.

SCRIPT:
{narration}

SOURCES:
{_sources_block(sources)}

Return: {{"verdict":"pass" or "fail","issues":["segment number: problem (in English)"]}}"""
    return ask_json(system, user, 2500)


def produce_script(story, sources, lane):
    script = write_script(story, sources, lane)
    check = fact_check(script, sources)
    if check.get("verdict") != "pass":
        log.info("fact-check issues, revising: %s", check.get("issues"))
        script = write_script(story, sources, lane, feedback=check.get("issues"))
        check = fact_check(script, sources)
    return script, check
