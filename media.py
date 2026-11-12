"""Steps 6-7: Telugu voice-over + faceless video (images + headline + zoom) + thumbnail."""
import asyncio, random, subprocess, hashlib, xml.sax.saxutils as sx
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont, features
from common import env, log
import imagegen

W, H = 1280, 720
FPS = 25


# ------------------------------------------------------------------ voice
def tts(text: str, out_path: Path):
    provider = env("TTS_PROVIDER", "edge")
    voice = env("TTS_VOICE", "te-IN-ShrutiNeural")
    if provider == "azure":
        ssml = (f"<speak version='1.0' xml:lang='te-IN'><voice name='{voice}'>"
                f"<prosody rate='-3%'>{sx.escape(text)}</prosody></voice></speak>")
        r = requests.post(
            f"https://{env('AZURE_SPEECH_REGION')}.tts.speech.microsoft.com/cognitiveservices/v1",
            headers={
                "Ocp-Apim-Subscription-Key": env("AZURE_SPEECH_KEY"),
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "audio-24khz-96kbitrate-mono-mp3",
                "User-Agent": "telugu-news-agent",
            },
            data=ssml.encode("utf-8"), timeout=120)
        r.raise_for_status()
        out_path.write_bytes(r.content)
    else:
        import edge_tts
        asyncio.run(edge_tts.Communicate(text, voice, rate="-3%").save(str(out_path)))


def duration(path: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    return float(out.decode().strip())


# ------------------------------------------------------------------ images
def pexels_image(query: str, cache_dir: Path):
    key = env("PEXELS_API_KEY")
    if not key:
        return None
    try:
        r = requests.get("https://api.pexels.com/v1/search",
                         headers={"Authorization": key},
                         params={"query": query, "per_page": 6, "orientation": "landscape"}, timeout=30)
        photos = r.json().get("photos", [])
        if not photos:
            return None
        url = random.choice(photos)["src"]["large2x"]
        p = cache_dir / (hashlib.md5(url.encode()).hexdigest() + ".jpg")
        if not p.exists():
            p.write_bytes(requests.get(url, timeout=60).content)
        return p
    except Exception as e:  # noqa
        log.warning("pexels failed for '%s': %s", query, e)
        return None


def _font(size):
    path = env("FONT_PATH", "./NotoSansTelugu-Bold.ttf")
    try:
        if features.check("raqm"):
            f = ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)
        else:
            log.warning("libraqm missing: Telugu conjuncts may render wrongly. Install libraqm (see README).")
            f = ImageFont.truetype(path, size)
        try:  # the downloaded font is a variable font: pick the bold style
            f.set_variation_by_name("Bold")
        except Exception:
            pass
        return f
    except OSError:
        raise SystemExit(f"Telugu font not found at {path}. Download Noto Sans Telugu and set FONT_PATH.")


def _wrap(font, text, max_w, max_lines):
    lines, cur = [], ""
    for w in text.split():
        t = f"{cur} {w}".strip()
        if font.getlength(t) <= max_w:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines[:max_lines]


def make_frame(bg_path, text, out_path: Path, big=False):
    if bg_path:
        img = Image.open(bg_path).convert("RGB")
        scale = max(W / img.width, H / img.height)
        img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1))
        l, t = (img.width - W) // 2, (img.height - H) // 2
        img = img.crop((l, t, l + W, t + H))
    else:
        img = Image.new("RGB", (W, H), (18, 28, 56))
    # dark gradient from the bottom for readable text
    grad = Image.new("L", (1, H))
    for y in range(H):
        grad.putpixel((0, y), int(min(235, max(0, (y - H * (0.25 if big else 0.5)) / (H * 0.5) * 235))))
    img.paste(Image.new("RGB", (W, H), (0, 0, 0)), (0, 0), grad.resize((W, H)))
    d = ImageDraw.Draw(img)
    size = 76 if big else 46
    font = _font(size)
    lines = _wrap(font, text, W - 140, 3)
    line_h = int(size * 1.45)
    y = H - 70 - line_h * len(lines)
    d.rectangle([40, y - 12, 50, y + line_h * len(lines)], fill=(230, 40, 40))
    for ln in lines:
        d.text((70, y), ln, font=font, fill=(255, 255, 255))
        y += line_h
    if env("SHOW_AI_LABEL", "true").lower() == "true" and not big:
        small = _font(20)
        d.text((40, 28), "AI illustration", font=small, fill=(220, 220, 220))
    # channel tag
    tag = _font(26)
    d.text((W - 40 - tag.getlength(env("CHANNEL_NAME", "")), 28), env("CHANNEL_NAME", ""),
           font=tag, fill=(255, 255, 255))
    img.save(out_path)


# ------------------------------------------------------------------ assemble
def _prep_segment(i, seg, workdir, cache):
    audio = workdir / f"a{i}.mp3"
    tts(seg["narration_te"], audio)
    bg = imagegen.generate(seg.get("image_prompt_en") or seg.get("image_query_en", "abstract"), cache) \
        or pexels_image(seg.get("image_query_en", "news"), cache)
    return audio, duration(audio) + 0.35, bg


def build_video(script: dict, workdir: Path) -> tuple[Path, Path]:
    workdir.mkdir(parents=True, exist_ok=True)
    cache = workdir.parent / "_img_cache"
    cache.mkdir(exist_ok=True)
    segs = script["segments"]
    # voice + AI images for all segments in parallel (the slow part)
    with ThreadPoolExecutor(max_workers=4) as ex:
        prepared = list(ex.map(lambda a: _prep_segment(a[0], a[1], workdir, cache), enumerate(segs)))
    clips, first_bg = [], None
    for i, (seg, (audio, dur, bg)) in enumerate(zip(segs, prepared)):
        first_bg = first_bg or bg
        frame = workdir / f"f{i}.png"
        make_frame(bg, seg["headline_te"], frame)
        clip = workdir / f"c{i}.mp4"
        n = int(dur * FPS) + 1
        # alternate slow zoom-in / zoom-out so consecutive images feel different
        z = "min(1+0.0005*on,1.12)" if i % 2 == 0 else "max(1.12-0.0005*on,1.0)"
        vf = (f"[0:v]scale=1920:-2,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':"
              f"y='ih/2-(ih/zoom/2)':d={n}:s={W}x{H}:fps={FPS},format=yuv420p[v];"
              f"[1:a]apad=pad_dur=0.35[a]")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(frame), "-i", str(audio),
                        "-filter_complex", vf, "-map", "[v]", "-map", "[a]",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
                        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
                        "-t", f"{dur:.2f}", str(clip)], check=True)
        clips.append(clip)
    lst = workdir / "list.txt"
    lst.write_text("".join(f"file '{c.name}'\n" for c in clips))
    joined = workdir / "joined.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", str(joined)], check=True)
    video = workdir / "final.mp4"
    music = env("MUSIC_PATH")
    if music and Path(music).exists():
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(joined), "-stream_loop", "-1", "-i", music,
                        "-filter_complex", "[1:a]volume=0.07[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]",
                        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", str(video)],
                       check=True)
    else:
        joined.rename(video)
    # thumbnail: its own AI image + big punchy text
    thumb_bg = imagegen.generate(script.get("thumbnail_prompt_en") or segs[0].get("image_prompt_en", "news"), cache) or first_bg
    make_frame(thumb_bg, script.get("thumbnail_text_te") or script["title_te"], workdir / "thumb.png", big=True)
    thumb = workdir / "thumb.jpg"
    Image.open(workdir / "thumb.png").convert("RGB").save(thumb, quality=88)
    return video, thumb


def make_preview(video: Path) -> Path:
    """Smaller copy to fit Telegram's 50 MB bot upload limit."""
    out = video.with_name("preview.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vf", "scale=854:-2",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "32",
                    "-c:a", "aac", "-b:a", "64k", str(out)], check=True)
    return out
