import os
import requests
import logging


from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)




# ─── Logging Setup ──────────────────────────────────────────────────────────────
#logging.basicConfig(
#    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
#    level=logging.INFO,
#)
#logger = logging.getLogger(__name__)

# ─── Environment Variables ───────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
YOUTUBE_API_KEY  = os.environ["YOUTUBE_API_KEY"]
CHANNEL_ID       = os.environ["YOUTUBE_CHANNEL_ID"]

# ─── Global State ─────────────────────────────────────────────────────────────────
subscribers: set[int] = set()
last_live_video_id: str | None = None


# ─── NOTIFY FUNCTION (async) ────────────────────────────────────────────────────
async def notify_subscribers(live_url: str):
    if not subscribers:
        #logger.info("No subscribers to notify.")
        return

    for chat_id in subscribers:
        try:
            await application.bot.send_message(
                chat_id=chat_id,
                text=f"📺 بدأ البث المباشر !\n\n🔗 {live_url}"
            )
            #logger.info(f"Notification sent to {chat_id}")
        except Exception as e:
            #logger.error(f"Failed to send notification to {chat_id}: {e}")
            pass


# ─── YOUTUBE‐LIVE‐CHECK LOOP (async) ──────────────────────────────────────────────
async def check_youtube_live_loop(context: ContextTypes.DEFAULT_TYPE):
    """
    JobQueue will call this every interval. Must accept one 'context' parameter.
    """
    global last_live_video_id

    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "channelId": CHANNEL_ID,
        "eventType": "live",
        "type": "video",
        "key": YOUTUBE_API_KEY
    }

    #logger.info("➤ Checking YouTube live status…")
    try:
        # Use requests in a thread so as not to block PTB's loop:
        from asyncio import get_running_loop
        loop = get_running_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: requests.get(url, params=params, timeout=(15, 15))
        )

        logger.info(f"  → YouTube API HTTP {resp.status_code}")
        data = resp.json()

        if resp.status_code != 200:
            #logger.warning(f"  » Non-200 from YouTube: {data}")
            return

        items = data.get("items", [])
        #logger.info(f"  » items returned: {len(items)}")
        if not items:
            last_live_video_id = None
            return

        video_id = items[0]["id"]["videoId"]
        live_url = f"https://youtu.be/{video_id}"

        #if video_id != last_live_video_id:
            #last_live_video_id = video_id
            #logger.info(f"  → Channel is LIVE! Notifying: {live_url}")
        await notify_subscribers(live_url)
        #else:
            #logger.info("  » Still the same live; no new notification.")
    except requests.exceptions.ConnectTimeout:
        pass
    except requests.exceptions.ReadTimeout:
        pass
    except Exception as e:
        pass

# ─── COMMAND HANDLERS ────────────────────────────────────────────────────────────
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 مرحبًا! اضغط الأمر /subscribe لتصلك إشعارات عندما يبدأ البث المباشر على القناة."
    )


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in subscribers:
        await update.message.reply_text("✅ أنت مشترك بالفعل")
        #logger.info(f"subscribe_command: {chat_id} already in the set.")
    else:
        subscribers.add(chat_id)
        await update.message.reply_text(
            "✅ تم الاشتراك! سأقوم بإعلامك عندما تبدأ القناة البث المباشر."
        )
        #logger.info(
        #    f"subscribe_command: NEW subscriber → {chat_id} "
        #    f"(total subscribers = {len(subscribers)})"
        #)


if __name__ == "__main__":
    # 1) Build the Application
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # 2) Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("subscribe", subscribe_command))

    # 3) Schedule check_youtube_live_loop every 60s, start immediately
    application.job_queue.run_repeating(
        callback=check_youtube_live_loop,
        interval=60.0,
        first=0.0,
    )

    # 4) Start polling (this also starts the JobQueue scheduler)
    #logger.info("Bot started. Polling for updates…")
    application.run_polling()

    # Start Uvicorn so FastAPI listens on $PORT:
    #port = int(os.environ.get("PORT", 8000))
    #uvicorn.run(app, host="0.0.0.0", port=port)