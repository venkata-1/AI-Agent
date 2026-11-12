"""Step 9: upload an APPROVED video to YouTube."""
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from common import BASE, env, log

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN = BASE / "token.json"
SECRETS = BASE / "client_secret.json"


def authorize():
    """Run once on a machine with a browser: python main.py auth"""
    flow = InstalledAppFlow.from_client_secrets_file(str(SECRETS), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN.write_text(creds.to_json())
    print("Saved token.json. Copy it to your server next to main.py.")


def _service():
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def upload_video(meta: dict) -> str:
    yt = _service()
    s = meta["script"]
    sources = "\n".join(f"• {x['source']}: {x['title']}" for x in meta["sources"][:5])
    description = (f"{s['description_te']}\n\nమూలాలు / Sources:\n{sources}\n\n"
                   "ఈ వీడియోలో AI ద్వారా రూపొందించిన వాయిస్ మరియు చిత్రాలు ఉపయోగించబడ్డాయి. "
                   "(AI-generated narration and illustrations; reviewed and approved by the channel owner.)")
    body = {
        "snippet": {
            "title": s["title_te"][:100],
            "description": description[:4900],
            "tags": s["tags"][:15],
            "categoryId": "25" if meta.get("lane") == "news" else "27",   # News & Politics / Education
            "defaultLanguage": "te",
            "defaultAudioLanguage": "te",
        },
        "status": {
            "privacyStatus": env("UPLOAD_PRIVACY", "public"),
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,   # YouTube's altered/synthetic disclosure
        },
    }
    media = MediaFileUpload(meta["video"], chunksize=-1, resumable=True, mimetype="video/mp4")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    vid = resp["id"]
    try:
        yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(meta["thumb"])).execute()
    except Exception as e:  # thumbnails need a verified channel
        log.warning("thumbnail not set: %s", e)
    return f"https://youtu.be/{vid}"
