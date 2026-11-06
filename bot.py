import os
import sys
import argparse
import time
import io
import re
from voicelm_engine import VoiceLMTTS, SPEAKERS_INFO

# Try importing telegram
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
except ImportError:
    print("python-telegram-bot not installed. Installing it or run: pip install python-telegram-bot")

# Global engine instance (loaded once on startup)
engine = None
user_speakers = {} # user_id -> speaker_id (default 'star04')

def get_engine():
    global engine
    if engine is None:
        engine = VoiceLMTTS()
    return engine

def get_speaker_keyboard():
    buttons = []
    row = []
    for spk_id, info in SPEAKERS_INFO.items():
        label = f"{'👩' if info['gender'] == 'female' else '👨'} {info['desc']} ({spk_id})"
        row.append(InlineKeyboardButton(label, callback_data=f"spk_{spk_id}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = (
        "👋 **أهلاً بك في بوت التوليد الصوتي VoiceLM**\n\n"
        "أنا بوت مخصص لتحويل النصوص العربية المشكّلة وغير المشكّلة إلى كلام فصيح عالي الدقة، "
        "أعمل على معالجات **CPU** عبر مكتبات النماذج العصبية الخفيفة.\n\n"
        "🎙 **كيفية الاستخدام:**\n"
        "1. أرسل أي نص عربي وسأقوم بنطقه وإرسال ملف الصوت فوراً.\n"
        "2. استخدم الأمر /voice لاختيار نبرة الصوت من بين 8 أصوات عربية (ذكورية وأنثوية).\n"
        "3. استخدم الأمر /help لمعرفة المزيد."
    )
    await update.message.reply_text(welcome_msg, parse_mode="Markdown")

async def voice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current_spk = user_speakers.get(user_id, 'star04')
    msg = f"🎙 **اختر الصوت المفضل لديك:**\nالصوت الحالي: `{current_spk}` ({SPEAKERS_INFO.get(current_spk, {}).get('desc', '')})"
    await update.message.reply_text(msg, reply_markup=get_speaker_keyboard(), parse_mode="Markdown")

async def voice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    spk_id = query.data.replace("spk_", "")
    if spk_id in SPEAKERS_INFO:
        user_speakers[user_id] = spk_id
        desc = SPEAKERS_INFO[spk_id]['desc']
        gender = "أنثوي" if SPEAKERS_INFO[spk_id]['gender'] == 'female' else "ذكوري"
        await query.edit_message_text(f"✅ تم ضبط الصوت بنجاح: **{desc}** ({gender} - `{spk_id}`)", parse_mode="Markdown")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    if not text or len(text.strip()) == 0:
        return
        
    spk_id = user_speakers.get(user_id, 'star04')
    status_msg = await update.message.reply_text("⏳ جاري توليد الصوت بواسطة VoiceLM على CPU...")
    
    try:
        t0 = time.time()
        eng = get_engine()
        out_wav = f"temp_{user_id}_{int(time.time())}.wav"
        eng.synthesize(text, speaker=spk_id, out_wav=out_wav)
        elapsed = time.time() - t0
        
        with open(out_wav, "rb") as audio_file:
            caption = f"🎙 تم التوليد بصوت: `{spk_id}` | ⏱ استغرق: {elapsed:.2f} ثانية"
            await update.message.reply_voice(voice=audio_file, caption=caption, parse_mode="Markdown")
            
        if os.path.exists(out_wav):
            os.remove(out_wav)
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"❌ حدث خطأ أثناء التوليد: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="VoiceLM Telegram Bot")
    parser.add_argument("--token", type=str, default=os.environ.get("BOT_TOKEN"), help="Telegram Bot Token")
    args = parser.parse_args()
    
    token = args.token
    if not token:
        print("Error: No bot token provided. Specify --token <TOKEN> or set BOT_TOKEN env variable.")
        sys.exit(1)
        
    print("[VoiceLM Bot] Pre-loading neural models...")
    get_engine()
    print("[VoiceLM Bot] Models ready. Starting Telegram polling...")
    
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("voice", voice_cmd))
    app.add_handler(CallbackQueryHandler(voice_callback, pattern="^spk_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    app.run_polling()

if __name__ == "__main__":
    main()
