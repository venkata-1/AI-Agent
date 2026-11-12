"""Step 8/9: send each finished video to the owner on Telegram; upload only after approval."""
import asyncio, io, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes
from common import env, load_state, save_state, log
import pipeline
from media import make_preview
from youtube import upload_video

OWNER = int(env("OWNER_CHAT_ID", "0"))
_running = False


def _owner_only(update: Update) -> bool:
    return update.effective_chat and update.effective_chat.id == OWNER


async def send_for_approval(app: Application, meta: dict):
    video = Path(meta["video"])
    if video.stat().st_size > 48 * 1024 * 1024:
        video = make_preview(video)
    flag = "✅ confirmed by 2+ sources" if meta["confirmed"] else "⚠️ only 1 source - verify yourself"
    check = "✅ fact-check passed" if meta["check"].get("verdict") == "pass" else "⚠️ fact-check issues (see below)"
    icon = "📰 NEWS" if meta.get("lane") == "news" else "🧠 EXPLAINER"
    caption = (f"{icon}: {meta['script']['title_te']}\n\n[{meta['category']}] {meta['topic']}\n{flag}\n{check}")[:1000]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve & upload", callback_data=f"ok:{meta['id']}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"no:{meta['id']}"),
    ]])
    with open(video, "rb") as f:
        await app.bot.send_video(OWNER, f, caption=caption, reply_markup=kb, supports_streaming=True,
                                 read_timeout=600, write_timeout=600, connect_timeout=60)
    narration = "\n\n".join(s["narration_te"] for s in meta["script"]["segments"])
    doc = io.BytesIO((meta["script"]["title_te"] + "\n\n" + narration).encode("utf-8"))
    await app.bot.send_document(OWNER, doc, filename=f"script_{meta['id']}.txt", caption="Full Telugu script for review")
    srcs = "\n".join(f"• {s['source']}: {s['title']}\n  {s['url']}" for s in meta["sources"])
    issues = "\n".join(f"• {i}" for i in meta["check"].get("issues", [])) or "none"
    await app.bot.send_message(OWNER, f"Sources for “{meta['topic']}”:\n{srcs}\n\nFact-check notes:\n{issues}"[:4000],
                               disable_web_page_preview=True)


async def run_batch(app: Application):
    global _running
    if _running:
        await app.bot.send_message(OWNER, "A run is already in progress.")
        return
    _running = True
    try:
        await app.bot.send_message(OWNER, "🔎 Collecting today's news…")
        stories = await asyncio.to_thread(pipeline.plan)
        await app.bot.send_message(OWNER, f"Picked {len(stories)} topics. Building videos - they'll arrive one by one.")
        for story in stories:
            try:
                meta = await asyncio.to_thread(pipeline.build, story)
                if meta:
                    await send_for_approval(app, meta)
            except Exception as e:  # noqa
                log.exception("story failed")
                await app.bot.send_message(OWNER, f"❌ Failed on '{story['topic_en']}': {e}")
        await app.bot.send_message(OWNER, "✅ Batch finished.")
    except Exception as e:  # noqa
        log.exception("batch failed")
        await app.bot.send_message(OWNER, f"❌ Batch failed: {e}")
    finally:
        _running = False


# ---------------- handlers
async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not _owner_only(update):
        return await q.answer("Not authorised.", show_alert=True)
    action, vid = q.data.split(":")
    state = load_state()
    meta = state["pending"].get(vid)
    if not meta or meta["status"] != "pending":
        return await q.answer("Already handled.", show_alert=True)
    await q.answer()
    if action == "no":
        meta["status"] = "rejected"
        save_state(state)
        await q.edit_message_reply_markup(None)
        return await q.message.reply_text("❌ Rejected. Nothing uploaded.")
    meta["status"] = "uploading"
    save_state(state)
    await q.edit_message_reply_markup(None)
    await q.message.reply_text("⏫ Uploading to YouTube…")
    try:
        url = await asyncio.to_thread(upload_video, meta)
        meta["status"], meta["url"] = "published", url
        await q.message.reply_text(f"🎉 Published: {url}")
    except Exception as e:  # noqa
        meta["status"] = "pending"
        await q.message.reply_text(f"❌ Upload failed: {e}\nTap Approve again after fixing.")
    save_state(state)


async def cmd_runnow(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if _owner_only(update):
        asyncio.create_task(run_batch(ctx.application))


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if _owner_only(update):
        st = load_state()["pending"].values()
        counts = {}
        for m in st:
            counts[m["status"]] = counts.get(m["status"], 0) + 1
        await update.message.reply_text(f"Videos: {counts or 'none yet'}\nRunning now: {_running}")


async def scheduled(ctx: ContextTypes.DEFAULT_TYPE):
    await run_batch(ctx.application)


def start():
    app = Application.builder().token(env("TELEGRAM_BOT_TOKEN")).build()
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(CommandHandler("runnow", cmd_runnow))
    app.add_handler(CommandHandler("status", cmd_status))
    tz = ZoneInfo(env("TIMEZONE", "Asia/Kolkata"))
    app.job_queue.run_daily(scheduled, time=dt.time(int(env("RUN_HOUR", "7")), int(env("RUN_MINUTE", "0")), tzinfo=tz))
    log.info("bot running. Daily run at %s:%s %s", env("RUN_HOUR", "7"), env("RUN_MINUTE", "0"), tz)
    app.run_polling()
