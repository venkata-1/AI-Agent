"""Glue: plan the day's videos (news lane + explainer lane), then build one video per topic."""
import time, uuid
from common import OUT, env, load_state, save_state, log
from collect import collect, trending_terms
from writer import pick_stories, pick_topics, gather_sources, produce_script
from media import build_video

_cache = {"items": []}
MIN_CHARS = {"news": 300, "explainer": 1500}


def plan():
    state = load_state()
    items = collect()
    _cache["items"] = items
    trends = trending_terms()
    n_news, n_expl = int(env("NEWS_VIDEOS", "2")), int(env("EXPLAINER_VIDEOS", "3"))
    news = pick_stories(items, state["covered"], n_news, trends) if n_news else []
    expl = pick_topics(items, state["covered"], n_expl, trends) if n_expl else []
    for s in news:
        s["lane"] = "news"
    for s in expl:
        s["lane"] = "explainer"
    # interleave so the Telegram feed alternates between lanes
    stories = [x for pair in zip(expl, news) for x in pair] + expl[len(news):] + news[len(expl):]
    log.info("today's plan: %s", [(s["lane"], s["topic_en"]) for s in stories])
    return stories


def script_only(story):
    lane = story["lane"]
    sources = gather_sources(story, _cache["items"], lane)
    if sum(len(s["text"]) for s in sources) < MIN_CHARS[lane]:
        return None
    script, check = produce_script(story, sources, lane)
    return {"story": story, "sources": sources, "script": script, "check": check}


def build(story):
    """Returns meta dict (ready for approval) or None if skipped for thin sources."""
    r = script_only(story)
    if not r:
        log.warning("skipping '%s': not enough source text to stay accurate", story["topic_en"])
        return None
    vid_id = uuid.uuid4().hex[:8]
    video, thumb = build_video(r["script"], OUT / f"{time.strftime('%Y%m%d')}_{vid_id}")
    meta = {
        "id": vid_id, "status": "pending", "video": str(video), "thumb": str(thumb),
        "lane": story["lane"], "topic": story["topic_en"], "category": story["category"],
        "confirmed": story["confirmed"], "script": r["script"],
        "sources": [{k: s[k] for k in ("source", "title", "url")} for s in r["sources"]],
        "check": r["check"],
    }
    state = load_state()
    state["pending"][vid_id] = meta
    state["covered"].append(story["topic_en"])
    state["covered"] = state["covered"][-300:]
    save_state(state)
    return meta
