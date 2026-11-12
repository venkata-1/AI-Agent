"""AI image generation (Gemini or OpenAI) with caching and Pexels fallback."""
import base64, hashlib
from pathlib import Path
from common import env, log

NEGATIVE = ("No text, no letters, no captions, no logos, no watermark. "
            "Do not depict any real identifiable person; use anonymous figures, silhouettes or symbolic imagery.")


def _full_prompt(scene: str) -> str:
    return f"{scene}. Style: {env('IMAGE_STYLE', 'cinematic digital illustration, dramatic lighting, 16:9 widescreen')}. {NEGATIVE}"


def _gemini(prompt, out: Path) -> bool:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=env("GEMINI_API_KEY"))
    model = env("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    try:
        resp = client.models.generate_content(
            model=model, contents=[prompt],
            config=types.GenerateContentConfig(image_config=types.ImageConfig(aspect_ratio="16:9")))
    except Exception:
        resp = client.models.generate_content(model=model, contents=[prompt])
    for cand in resp.candidates or []:
        for part in cand.content.parts or []:
            if getattr(part, "inline_data", None) and part.inline_data.data:
                out.write_bytes(part.inline_data.data)
                return True
    return False


def _openai(prompt, out: Path) -> bool:
    from openai import OpenAI
    r = OpenAI(api_key=env("OPENAI_API_KEY")).images.generate(
        model=env("OPENAI_IMAGE_MODEL", "gpt-image-1"), prompt=prompt, size="1536x1024", quality="medium", n=1)
    out.write_bytes(base64.b64decode(r.data[0].b64_json))
    return True


def generate(scene: str, cache_dir: Path):
    """Returns path to a generated image, or None (caller falls back to stock / plain background)."""
    provider = env("IMAGE_PROVIDER", "gemini").lower()
    if provider == "none":
        return None
    prompt = _full_prompt(scene)
    out = cache_dir / (hashlib.md5((provider + prompt).encode()).hexdigest() + ".png")
    if out.exists():
        return out
    for attempt in range(2):
        try:
            ok = _gemini(prompt, out) if provider == "gemini" else _openai(prompt, out)
            if ok:
                return out
        except Exception as e:  # noqa
            log.warning("image gen attempt %d failed: %s", attempt + 1, e)
    return None
