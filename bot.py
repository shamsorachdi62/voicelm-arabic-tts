#!/usr/bin/env python3
"""
VoiceLM Multilingual TTS Telegram Bot:
Ultra-minimal, zero stats, zero emojis, purely functional.
Supports 52 languages and 416 speaker voices.
"""

import os
import sys
import time
import argparse
import telebot
from telebot import types
from voicelm_engine import VoiceLMTTS, SPEAKERS_INFO

DEFAULT_TOKEN = os.environ.get("BOT_TOKEN", "9256956395:AAGYTGF2vYVMzGafGzKsDLseZh2JLEpfZyM")

POPULAR_LOCALES = {
    'auto': 'تلقائي',
    'ar_xa': 'العربية',
    'en_us': 'الإنجليزية',
    'fr_fr': 'الفرنسية',
    'es_es': 'الإسبانية',
    'de_de': 'الألمانية',
    'ru_ru': 'الروسية',
    'tr_tr': 'التركية',
    'it_it': 'الإيطالية',
    'ja_jp': 'اليابانية',
    'cmn_cn': 'الصينية',
    'ko_kr': 'الكورية',
}

engine = None
user_speakers = {}  # chat_id -> speaker_id
user_locales = {}   # chat_id -> locale_code (or None for auto)

def get_engine():
    global engine
    if engine is None:
        print("[VoiceLM] Loading models...", flush=True)
        engine = VoiceLMTTS()
        print("[VoiceLM] Models ready.", flush=True)
    return engine

def make_voice_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for spk_id, info in SPEAKERS_INFO.items():
        buttons.append(types.InlineKeyboardButton(f"{info['desc']} ({spk_id})", callback_data=f"spk_{spk_id}"))
    markup.add(*buttons)
    return markup

def make_lang_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for code, name in POPULAR_LOCALES.items():
        buttons.append(types.InlineKeyboardButton(name, callback_data=f"lng_{code}"))
    markup.add(*buttons)
    return markup

def create_bot(token):
    bot = telebot.TeleBot(token, parse_mode=None)

    @bot.message_handler(commands=['start', 'help'])
    def handle_start(message):
        bot.reply_to(message, "أرسل النص لتحويله إلى صوت، أو /voice لاختيار الصوت، أو /lang لاختيار اللغة.")

    @bot.message_handler(commands=['voice'])
    def handle_voice_cmd(message):
        bot.send_message(message.chat.id, "اختر الصوت:", reply_markup=make_voice_keyboard())

    @bot.message_handler(commands=['lang'])
    def handle_lang_cmd(message):
        bot.send_message(message.chat.id, "اختر اللغة:", reply_markup=make_lang_keyboard())

    @bot.callback_query_handler(func=lambda call: call.data.startswith('spk_'))
    def handle_voice_callback(call):
        spk_id = call.data.replace('spk_', '')
        if spk_id in SPEAKERS_INFO:
            user_speakers[call.message.chat.id] = spk_id
            info = SPEAKERS_INFO[spk_id]
            bot.answer_callback_query(call.id, f"تم اختيار {info['desc']}")
            bot.edit_message_text(
                f"تم اختيار {info['desc']}.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )

    @bot.callback_query_handler(func=lambda call: call.data.startswith('lng_'))
    def handle_lang_callback(call):
        code = call.data.replace('lng_', '')
        if code in POPULAR_LOCALES:
            user_locales[call.message.chat.id] = None if code == 'auto' else code
            name = POPULAR_LOCALES[code]
            bot.answer_callback_query(call.id, f"تم اختيار {name}")
            bot.edit_message_text(
                f"تم اختيار {name}.",
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
        loc = user_locales.get(chat_id, None)
        print(f"[Bot] Synthesizing for {chat_id}: '{text[:30]}...' ({spk_id}, loc={loc})", flush=True)
        
        try:
            bot.send_chat_action(chat_id, 'record_voice')
        except Exception:
            pass
            
        try:
            eng = get_engine()
            temp_wav = f"voice_{chat_id}_{int(time.time()*1000)}.wav"
            eng.synthesize(text, locale=loc, speaker=spk_id, out_wav=temp_wav)
            
            with open(temp_wav, "rb") as audio:
                try:
                    bot.send_voice(chat_id, audio, reply_to_message_id=message.message_id)
                except Exception:
                    audio.seek(0)
                    bot.send_audio(chat_id, audio, reply_to_message_id=message.message_id)
                    
            if os.path.exists(temp_wav):
                os.remove(temp_wav)
            print(f"[Bot] Sent voice to {chat_id}", flush=True)
        except Exception as e:
            print(f"[Bot] Error: {e}", flush=True)
            bot.reply_to(message, f"خطأ: {str(e)}")

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
