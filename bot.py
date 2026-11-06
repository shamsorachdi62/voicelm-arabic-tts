#!/usr/bin/env python3
"""
VoiceLM Arabic TTS Telegram Bot:
Runs on CPU locally or inside a Kaggle notebook.
"""

import os
import sys
import time
import argparse
import telebot
from telebot import types
from voicelm_engine import VoiceLMTTS, SPEAKERS_INFO

# Default token
DEFAULT_TOKEN = os.environ.get("BOT_TOKEN", "9256956395:AAGYTGF2vYVMzGafGzKsDLseZh2JLEpfZyM")

engine = None
user_speakers = {} # chat_id -> speaker_id

def get_engine():
    global engine
    if engine is None:
        print("[VoiceLM Bot] Loading models into memory...", flush=True)
        engine = VoiceLMTTS()
        print("[VoiceLM Bot] Models loaded successfully.", flush=True)
    return engine

def make_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for spk_id, info in SPEAKERS_INFO.items():
        icon = "👩" if info['gender'] == 'female' else "👨"
        text = f"{icon} {info['desc']} ({spk_id})"
        buttons.append(types.InlineKeyboardButton(text, callback_data=f"spk_{spk_id}"))
    markup.add(*buttons)
    return markup

def create_bot(token):
    bot = telebot.TeleBot(token, parse_mode="Markdown")

    @bot.message_handler(commands=['start', 'help'])
    def handle_start(message):
        print(f"[Bot] /start received from {message.chat.id}", flush=True)
        welcome_text = (
            "👋 **أهلاً بك في بوت التوليد الصوتي الذكي (VoiceLM)**\n\n"
            "أقوم بتحويل النصوص العربية (المشكّلة وغير المشكّلة) إلى صوت فصيح فائق الدقة، "
            "أعمل كلياً على معالجات **CPU** وبدون الحاجة إلى كروت شاشة.\n\n"
            "🎙 **التعليمات والأوامر:**\n"
            "• أرسل أي جملة أو نص عربي مباشرة لتوليده صوتياً.\n"
            "• استخدم الأمر /voice لاختيار النبرة من بين 8 أصوات فصيحة (ذكورية وأنثوية).\n"
            "• الصوت الافتراضي حالياً: **الصوت الإذاعي الوقور** (`star04`)."
        )
        bot.reply_to(message, welcome_text)

    @bot.message_handler(commands=['voice'])
    def handle_voice_cmd(message):
        print(f"[Bot] /voice received from {message.chat.id}", flush=True)
        current_spk = user_speakers.get(message.chat.id, 'star04')
        desc = SPEAKERS_INFO.get(current_spk, {}).get('desc', '')
        msg = f"🎙 **اختر الصوت المفضل لديك:**\nالصوت الحالي: `{current_spk}` ({desc})"
        bot.send_message(message.chat.id, msg, reply_markup=make_keyboard())

    @bot.callback_query_handler(func=lambda call: call.data.startswith('spk_'))
    def handle_voice_callback(call):
        spk_id = call.data.replace('spk_', '')
        if spk_id in SPEAKERS_INFO:
            user_speakers[call.message.chat.id] = spk_id
            info = SPEAKERS_INFO[spk_id]
            gender = "أنثوي" if info['gender'] == 'female' else "ذكوري"
            print(f"[Bot] Speaker changed to {spk_id} for chat {call.message.chat.id}", flush=True)
            bot.answer_callback_query(call.id, f"تم اختيار {info['desc']}")
            bot.edit_message_text(
                f"✅ تم ضبط الصوت بنجاح: **{info['desc']}** ({gender} - `{spk_id}`)",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )

    @bot.message_handler(func=lambda message: True)
    def handle_text_message(message):
        text = message.text.strip()
        if not text:
            return

        chat_id = message.chat.id
        spk_id = user_speakers.get(chat_id, 'star04')
        print(f"[Bot] Synthesizing text for {chat_id}: '{text[:40]}...' (speaker: {spk_id})", flush=True)
        
        status_msg = bot.reply_to(message, "⏳ جاري توليد الصوت باستخدام VoiceLM على CPU...")
        
        try:
            t0 = time.time()
            eng = get_engine()
            temp_wav = f"voice_{chat_id}_{int(time.time()*1000)}.wav"
            waveform = eng.synthesize(text, speaker=spk_id, out_wav=temp_wav)
            elapsed = time.time() - t0
            duration_s = len(waveform) / 24000.0
            print(f"[Bot] Synthesis completed in {elapsed:.2f}s (Audio: {duration_s:.1f}s)", flush=True)
            
            caption = f"🎙 الصوت: `{spk_id}` ({SPEAKERS_INFO.get(spk_id, {}).get('desc', '')})\n⏱ وقت التوليد: {elapsed:.2f} ثانية | ⏳ مدة الصوت: {duration_s:.1f} ثانية"
            
            with open(temp_wav, "rb") as audio:
                try:
                    bot.send_voice(chat_id, audio, caption=caption, reply_to_message_id=message.message_id)
                except Exception as ex_voice:
                    print(f"[Bot] send_voice fallback to send_audio: {ex_voice}", flush=True)
                    audio.seek(0)
                    bot.send_audio(chat_id, audio, caption=caption, reply_to_message_id=message.message_id, title="VoiceLM Output")
                    
            if os.path.exists(temp_wav):
                os.remove(temp_wav)
            bot.delete_message(chat_id, status_msg.message_id)
            print(f"[Bot] Audio sent successfully to {chat_id}", flush=True)
        except Exception as e:
            print(f"[Bot] Error during synthesis: {e}", flush=True)
            bot.edit_message_text(f"❌ حدث خطأ أثناء التوليد الصوتي: {str(e)}", chat_id=chat_id, message_id=status_msg.message_id)

    return bot

def main():
    parser = argparse.ArgumentParser(description="VoiceLM Telegram Bot")
    parser.add_argument("--token", type=str, default=DEFAULT_TOKEN, help="Telegram Bot Token")
    args = parser.parse_args()

    token = args.token
    if not token:
        print("Error: No bot token provided.", flush=True)
        sys.exit(1)

    print(f"[*] Initializing VoiceLM Telegram Bot with token: {token[:12]}...", flush=True)
    get_engine()
    print("[*] Engine pre-loaded and ready.", flush=True)

    bot = create_bot(token)
    print("[*] Bot is polling for Telegram messages...", flush=True)
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"[!] Polling error: {e}", flush=True)
            time.sleep(2)

if __name__ == "__main__":
    main()
