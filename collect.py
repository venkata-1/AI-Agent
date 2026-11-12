"""Step 1: collect topics.
 NEWS lane      : Google News RSS (Telugu + English, India + diaspora)
 DISCOVERY lane : NOT news channels - Wikipedia most-read + On-this-day, Reddit, Hacker News, NASA, ScienceDaily, Ars Technica
 Also: Google Trends (India/US) used as a 'what people are searching right now' hint.
"""
import datetime as dt
from urllib.parse import quote
import feedparser, requests, trafilatura
from common import log

UA = "TeluguNewsAgent/1.0 (personal YouTube project)"
GN = "https://news.google.com/rss"
TE = "hl=te&gl=IN&ceid=IN:te"
EN = "hl=en-IN&gl=IN&ceid=IN:en"

NEWS_FEEDS = [
    f"{GN}?{TE}", f"{GN}?{EN}",
    f"{GN}/search?q={quote('Telangana')}&{EN}",
    f"{GN}/search?q={quote('Andhra Pradesh')}&{EN}",
    f"{GN}/search?q={quote('Tollywood')}&{EN}",
    f"{GN}/search?q={quote('తెలుగు సినిమా')}&{TE}",
    f"{GN}/search?q={quote('Tirumala OR Telugu temple OR festival')}&{EN}",
    f"{GN}/search?q={quote('H-1B OR green card OR Indian students USA')}&{EN}",
    f"{GN}/search?q={quote('Telugu NRI OR Telugu diaspora OR TANA OR NATS')}&{EN}",
    f"{GN}/search?q={quote('Gulf Indian workers OR Telugu Gulf')}&{EN}",
    f"{GN}/search?q={quote('India cricket')}&{EN}",
    f"{GN}/search?q={quote('India economy OR Sensex OR RBI')}&{EN}",
]

REDDIT = ["todayilearned", "space", "history", "science", "Futurology", "geopolitics",
          "psychology", "UnresolvedMysteries", "interestingasfuck", "technology"]
RSS_DISCOVERY = {
    "NASA": "https://www.nasa.gov/feed/",
    "ScienceDaily": "https://www.sciencedaily.com/rss/top.xml",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
}
WIKI_SKIP = ("Main_Page", "Special:", "Wikipedia:", "Portal:", "File:", "Category:", "Help:", "Template:",
             "Talk:", "List_of", "Deaths_in", "-")


def _get(url, **kw):
    return requests.get(url, headers={"User-Agent": UA}, timeout=30, **kw)


def _split_source(title):
    headline, _, source = title.rpartition(" - ")
    return (headline, source) if headline else (title, "unknown")


# ------------------------------------------------------------------ news lane
def _collect_news(per_feed=15):
    out = []
    for url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception as e:  # noqa
            log.warning("feed failed: %s", e)
            continue
        for e in feed.entries[:per_feed]:
            title = e.get("title", "").strip()
            if title:
                h, s = _split_source(title)
                out.append({"title": h, "source": s, "link": e.get("link", ""), "lane": "news"})
    return out


# ------------------------------------------------------------------ discovery lane
def _wiki_most_read():
    out = []
    try:
        d = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
        r = _get(f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/{d:%Y/%m/%d}")
        for a in r.json()["items"][0]["articles"]:
            name = a["article"]
            if name.startswith(WIKI_SKIP[:-1]) or any(k in name for k in ("List_of", "Deaths_in")):
                continue
            t = name.replace("_", " ")
            out.append({"title": f"{t} (Wikipedia most-read yesterday)", "source": "Wikipedia trending",
                        "link": "", "wiki_title": t, "lane": "discovery"})
            if len(out) >= 35:
                break
    except Exception as e:  # noqa
        log.warning("wikipedia most-read failed: %s", e)
    return out


def _wiki_on_this_day():
    out = []
    try:
        d = dt.datetime.now(dt.timezone.utc)
        r = _get(f"https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/selected/{d:%m/%d}")
        for ev in r.json().get("selected", [])[:20]:
            pages = ev.get("pages") or []
            wt = pages[0]["titles"]["normalized"] if pages else None
            out.append({"title": f"On this day {ev['year']}: {ev['text']}", "source": "Wikipedia On This Day",
                        "link": "", "wiki_title": wt, "lane": "discovery"})
    except Exception as e:  # noqa
        log.warning("on-this-day failed: %s", e)
    return out


def _reddit():
    out = []
    for sub in REDDIT:
        try:
            feed = feedparser.parse(f"https://www.reddit.com/r/{sub}/top/.rss?t=day", agent=UA)
            for e in feed.entries[:6]:
                out.append({"title": e.get("title", ""), "source": f"Reddit r/{sub}", "link": "", "lane": "discovery"})
        except Exception as e:  # noqa
            log.warning("reddit %s failed: %s", sub, e)
    return out


def _hn():
    out = []
    try:
        ids = _get("https://hacker-news.firebaseio.com/v0/topstories.json").json()[:15]
        for i in ids:
            it = _get(f"https://hacker-news.firebaseio.com/v0/item/{i}.json").json()
            if it and it.get("url"):
                out.append({"title": it["title"], "source": "Hacker News", "link": it["url"], "lane": "discovery"})
    except Exception as e:  # noqa
        log.warning("hn failed: %s", e)
    return out


def _rss_discovery():
    out = []
    for name, url in RSS_DISCOVERY.items():
        try:
            for e in feedparser.parse(url, agent=UA).entries[:8]:
                out.append({"title": e.get("title", ""), "source": name, "link": e.get("link", ""), "lane": "discovery"})
        except Exception as e:  # noqa
            log.warning("%s failed: %s", name, e)
    return out


def collect():
    items, seen = [], set()
    for it in _collect_news() + _wiki_most_read() + _wiki_on_this_day() + _reddit() + _hn() + _rss_discovery():
        key = it["title"].lower()[:70]
        if not key or key in seen:
            continue
        seen.add(key)
        it["id"] = len(items)
        items.append(it)
    log.info("collected %d items (%d news, %d discovery)", len(items),
             sum(i["lane"] == "news" for i in items), sum(i["lane"] == "discovery" for i in items))
    return items


def trending_terms():
    terms = []
    for geo in ("IN", "US"):
        try:
            for e in feedparser.parse(f"https://trends.google.com/trending/rss?geo={geo}", agent=UA).entries[:15]:
                terms.append(e.get("title", ""))
        except Exception:
            pass
    return [t for t in terms if t]


# ------------------------------------------------------------------ article / wikipedia text
def _resolve(link):
    if "news.google.com" in link:
        try:
            from googlenewsdecoder import gnewsdecoder
            r = gnewsdecoder(link, interval=1)
            if r.get("status"):
                return r["decoded_url"]
        except Exception:
            pass
    return link


def fetch_article(link, limit=6000):
    if not link:
        return ""
    try:
        html = trafilatura.fetch_url(_resolve(link))
        text = trafilatura.extract(html, include_comments=False) if html else ""
        return (text or "")[:limit]
    except Exception as e:  # noqa
        log.warning("fetch failed: %s", e)
        return ""


def wiki_fetch(title, limit=12000):
    """Return (resolved_title, url, text) from English Wikipedia, or None."""
    try:
        r = _get("https://en.wikipedia.org/w/api.php", params={
            "action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1,
            "titles": title, "format": "json", "exsectionformat": "plain"})
        page = next(iter(r.json()["query"]["pages"].values()))
        if "missing" in page or not page.get("extract"):
            return None
        t = page["title"]
        return t, "https://en.wikipedia.org/wiki/" + quote(t.replace(" ", "_")), page["extract"][:limit]
    except Exception as e:  # noqa
        log.warning("wiki fetch failed for %s: %s", title, e)
        return None
