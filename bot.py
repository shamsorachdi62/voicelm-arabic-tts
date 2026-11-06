#!/usr/bin/env python3
"""
VoiceLM Arabic TTS Telegram Bot:
Concise, minimal, zero emojis.
"""

import os
import sys
import time
import argparse
import telebot
from telebot import types
from voicelm_engine import VoiceLMTTS, SPEAKERS_INFO

DEFAULT_TOKEN = os.environ.get("BOT_TOKEN", "9256956395:AAGYTGF2vYVMzGafGzKsDLseZh2JLEpfZyM")

engine = None
user_speakers = {} # chat_id -> speaker_id

def get_engine():
    global engine
    if engine is None:
        print("[VoiceLM] Loading models...", flush=True)
        engine = VoiceLMTTS()
        print("[VoiceLM] Models ready.", flush=True)
    return engine

def make_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for spk_id, info in SPEAKERS_INFO.items():
        text = f"{info['desc']} ({spk_id})"
        buttons.append(types.InlineKeyboardButton(text, callback_data=f"spk_{spk_id}"))
    markup.add(*buttons)
    return markup

def create_bot(token):
    bot = telebot.TeleBot(token, parse_mode="Markdown")

    @bot.message_handler(commands=['start', 'help'])
    def handle_start(message):
        bot.reply_to(message, "أرسل النص لتحويله إلى صوت، أو /voice لاختيار الصوت.")

    @bot.message_handler(commands=['voice'])
    def handle_voice_cmd(message):
        current_spk = user_speakers.get(message.chat.id, 'star04')
        desc = SPEAKERS_INFO.get(current_spk, {}).get('desc', '')
        msg = f"اختر الصوت (الحالي: {desc} - {current_spk}):"
        bot.send_message(message.chat.id, msg, reply_markup=make_keyboard())

    @bot.callback_query_handler(func=lambda call: call.data.startswith('spk_'))
    def handle_voice_callback(call):
        spk_id = call.data.replace('spk_', '')
        if spk_id in SPEAKERS_INFO:
            user_speakers[call.message.chat.id] = spk_id
            info = SPEAKERS_INFO[spk_id]
            bot.answer_callback_query(call.id, f"تم اختيار {info['desc']}")
            bot.edit_message_text(
                f"تم ضبط الصوت: {info['desc']} ({spk_id})",
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
        print(f"[Bot] Synthesizing for {chat_id}: '{text[:30]}...' ({spk_id})", flush=True)
        
        status_msg = bot.reply_to(message, "جاري التوليد...")
        
        try:
            t0 = time.time()
            eng = get_engine()
            temp_wav = f"voice_{chat_id}_{int(time.time()*1000)}.wav"
            waveform = eng.synthesize(text, speaker=spk_id, out_wav=temp_wav)
            elapsed = time.time() - t0
            duration_s = len(waveform) / 24000.0
            
            caption = f"الصوت: {spk_id} | التوليد: {elapsed:.1f} ثانية | المدة: {duration_s:.1f} ثانية"
            
            with open(temp_wav, "rb") as audio:
                try:
                    bot.send_voice(chat_id, audio, caption=caption, reply_to_message_id=message.message_id)
                except Exception:
                    audio.seek(0)
                    bot.send_audio(chat_id, audio, caption=caption, reply_to_message_id=message.message_id)
                    
            if os.path.exists(temp_wav):
                os.remove(temp_wav)
            bot.delete_message(chat_id, status_msg.message_id)
            print(f"[Bot] Sent to {chat_id} in {elapsed:.2f}s", flush=True)
        except Exception as e:
            print(f"[Bot] Error: {e}", flush=True)
            bot.edit_message_text(f"خطأ: {str(e)}", chat_id=chat_id, message_id=status_msg.message_id)

    return bot

def main():
    parser = argparse.ArgumentParser(description="VoiceLM Telegram Bot")
    parser.add_argument("--token", type=str, default=DEFAULT_TOKEN, help="Telegram Bot Token")
    args = parser.parse_args()

    token = args.token
    if not token:
        print("Error: No bot token provided.", flush=True)
        sys.exit(1)

    print(f"[*] Initializing VoiceLM Bot ({token[:10]}...)", flush=True)
    get_engine()
    bot = create_bot(token)
    print("[*] Bot running...", flush=True)
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"[!] Error: {e}", flush=True)
            time.sleep(2)

if __name__ == "__main__":
    main()
