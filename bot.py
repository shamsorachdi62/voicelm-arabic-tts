#!/usr/bin/env python3
"""
VoiceLM Multilingual TTS Telegram Bot:
Ultra-minimal, zero stats, zero emojis, purely functional.
Supports full parameter control: speed, pitch, guidance, temperature, locale, speaker.
Supports native Instant Zero-Shot Voice Cloning by sending any audio / voice note!
"""

import os
import sys
import time
import argparse
import telebot
from telebot import types
from voicelm_engine import VoiceLMTTS, SPEAKERS_INFO

DEFAULT_TOKEN = os.environ.get("BOT_TOKEN", "9256956395:AAGYTGF2vYVMzGafGzKsDLseZh2JLEpfZyM")

DEFAULT_CLONED_EMB = None
_cloned_model_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "user_cloned_voice.npy")
if os.path.exists(_cloned_model_file):
    try:
        import numpy as np
        DEFAULT_CLONED_EMB = np.load(_cloned_model_file)
        print(f"[Bot] Loaded pre-cloned speaker embedding: {DEFAULT_CLONED_EMB.shape}", flush=True)
    except Exception as _e:
        print(f"[Bot] Warning loading pre-cloned voice: {_e}", flush=True)

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
user_params = {}            # chat_id -> dict
user_custom_embeddings = {} # chat_id -> np.ndarray [1, T, 128]

DEFAULT_CONFIG = {
    'speaker': 'star04',
    'locale': None,
    'speed': 1.0,
    'pitch': 0.0,
    'cf_guidance': 2.2,
    'temperature': 0.4,
}

def get_config(chat_id):
    if chat_id not in user_params:
        user_params[chat_id] = DEFAULT_CONFIG.copy()
    return user_params[chat_id]

def set_config(chat_id, key, val):
    cfg = get_config(chat_id)
    cfg[key] = val

def get_engine():
    global engine
    if engine is None:
        print("[VoiceLM] Loading models...", flush=True)
        engine = VoiceLMTTS()
        print("[VoiceLM] Models ready.", flush=True)
    return engine

def make_voice_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = [types.InlineKeyboardButton("مستنسخ (Cloned)", callback_data="spk_cloned")]
    for spk_id in sorted(SPEAKERS_INFO.keys()):
        buttons.append(types.InlineKeyboardButton(spk_id, callback_data=f"spk_{spk_id}"))
    markup.add(*buttons)
    return markup

def make_lang_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for code, name in POPULAR_LOCALES.items():
        buttons.append(types.InlineKeyboardButton(name, callback_data=f"lng_{code}"))
    markup.add(*buttons)
    return markup

def make_speed_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("0.75x (بطيء)", callback_data="spd_0.75"),
        types.InlineKeyboardButton("1.0x (طبيعي)", callback_data="spd_1.0"),
        types.InlineKeyboardButton("1.25x (سريع)", callback_data="spd_1.25"),
        types.InlineKeyboardButton("1.5x (أسرع)", callback_data="spd_1.5"),
    ]
    markup.add(*buttons)
    return markup

def make_pitch_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = [
        types.InlineKeyboardButton("-3 (أغلظ)", callback_data="ptc_-3"),
        types.InlineKeyboardButton("0 (طبيعي)", callback_data="ptc_0"),
        types.InlineKeyboardButton("+3 (أحدّ)", callback_data="ptc_3"),
    ]
    markup.add(*buttons)
    return markup

def create_bot(token):
    bot = telebot.TeleBot(token, parse_mode=None)

    @bot.message_handler(commands=['start', 'help'])
    def handle_start(message):
        bot.reply_to(
            message,
            "أرسل النص لتحويله إلى صوت مباشرة، أو أرسل أي تسجيل صوتي لاستنساخه والتحدث به فوراً.\n"
            "الأوامر: /voice /clone /lang /speed /pitch /guidance /temp /settings /reset"
        )

    @bot.message_handler(commands=['clone'])
    def handle_clone_cmd(message):
        set_config(message.chat.id, 'speaker', 'cloned')
        bot.reply_to(
            message,
            "تم تفعيل وضع استنساخ الصوت.\n"
            "أرسل أي تسجيل صوتي لاستنساخ نبرتك، أو أرسل نصاً للتحدث بالصوت المستنسخ المعتمد."
        )

    @bot.message_handler(commands=['voice'])
    def handle_voice_cmd(message):
        bot.send_message(message.chat.id, "اختر الصوت:", reply_markup=make_voice_keyboard())

    @bot.message_handler(commands=['lang'])
    def handle_lang_cmd(message):
        bot.send_message(message.chat.id, "اختر اللغة:", reply_markup=make_lang_keyboard())

    @bot.message_handler(commands=['speed'])
    def handle_speed_cmd(message):
        parts = message.text.strip().split()
        if len(parts) > 1:
            try:
                val = float(parts[1])
                val = max(0.5, min(val, 2.0))
                set_config(message.chat.id, 'speed', val)
                bot.reply_to(message, f"تم ضبط السرعة: {val:.2f}x")
                return
            except ValueError:
                pass
        bot.send_message(message.chat.id, "اختر السرعة:", reply_markup=make_speed_keyboard())

    @bot.message_handler(commands=['pitch'])
    def handle_pitch_cmd(message):
        parts = message.text.strip().split()
        if len(parts) > 1:
            try:
                val = float(parts[1])
                val = max(-6.0, min(val, 6.0))
                set_config(message.chat.id, 'pitch', val)
                bot.reply_to(message, f"تم ضبط الحدة: {val:+.1f}")
                return
            except ValueError:
                pass
        bot.send_message(message.chat.id, "اختر الحدة:", reply_markup=make_pitch_keyboard())

    @bot.message_handler(commands=['guidance'])
    def handle_guidance_cmd(message):
        parts = message.text.strip().split()
        if len(parts) > 1:
            try:
                val = float(parts[1])
                val = max(1.0, min(val, 5.0))
                set_config(message.chat.id, 'cf_guidance', val)
                bot.reply_to(message, f"تم ضبط التوجيه: {val:.1f}")
                return
            except ValueError:
                pass
        bot.reply_to(message, "أرسل القيمة بعد الأمر من 1.0 إلى 5.0 (مثال: /guidance 2.5)")

    @bot.message_handler(commands=['temp'])
    def handle_temp_cmd(message):
        parts = message.text.strip().split()
        if len(parts) > 1:
            try:
                val = float(parts[1])
                val = max(0.1, min(val, 1.0))
                set_config(message.chat.id, 'temperature', val)
                bot.reply_to(message, f"تم ضبط الحرارة: {val:.2f}")
                return
            except ValueError:
                pass
        bot.reply_to(message, "أرسل القيمة بعد الأمر من 0.1 إلى 1.0 (مثال: /temp 0.4)")

    @bot.message_handler(commands=['settings'])
    def handle_settings_cmd(message):
        cfg = get_config(message.chat.id)
        loc = cfg['locale'] if cfg['locale'] else "تلقائي"
        spk = "مستنسخ مخصص (Cloned)" if cfg['speaker'] == 'cloned' else cfg['speaker']
        msg = (
            f"الصوت: {spk}\n"
            f"اللغة: {loc}\n"
            f"السرعة: {cfg['speed']:.2f}x\n"
            f"الحدة: {cfg['pitch']:+.1f}\n"
            f"التوجيه: {cfg['cf_guidance']:.1f}\n"
            f"الحرارة: {cfg['temperature']:.2f}"
        )
        bot.reply_to(message, msg)

    @bot.message_handler(commands=['reset'])
    def handle_reset_cmd(message):
        user_params[message.chat.id] = DEFAULT_CONFIG.copy()
        user_custom_embeddings.pop(message.chat.id, None)
        bot.reply_to(message, "تمت استعادة الإعدادات الافتراضية.")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('spk_'))
    def handle_voice_callback(call):
        spk_id = call.data.replace('spk_', '')
        if spk_id == 'cloned':
            set_config(call.message.chat.id, 'speaker', 'cloned')
            bot.answer_callback_query(call.id, "تم تفعيل الصوت المستنسخ")
            bot.edit_message_text("تم اختيار: الصوت المستنسخ (Cloned).", chat_id=call.message.chat.id, message_id=call.message.message_id)
        elif spk_id in SPEAKERS_INFO:
            set_config(call.message.chat.id, 'speaker', spk_id)
            user_custom_embeddings.pop(call.message.chat.id, None)
            bot.answer_callback_query(call.id, f"تم اختيار {spk_id}")
            bot.edit_message_text(f"تم اختيار: {spk_id}.", chat_id=call.message.chat.id, message_id=call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('lng_'))
    def handle_lang_callback(call):
        code = call.data.replace('lng_', '')
        if code in POPULAR_LOCALES:
            loc = None if code == 'auto' else code
            set_config(call.message.chat.id, 'locale', loc)
            name = POPULAR_LOCALES[code]
            bot.answer_callback_query(call.id, f"تم اختيار {name}")
            bot.edit_message_text(f"تم اختيار {name}.", chat_id=call.message.chat.id, message_id=call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('spd_'))
    def handle_speed_callback(call):
        val = float(call.data.replace('spd_', ''))
        set_config(call.message.chat.id, 'speed', val)
        bot.answer_callback_query(call.id, f"السرعة: {val:.2f}x")
        bot.edit_message_text(f"تم ضبط السرعة: {val:.2f}x.", chat_id=call.message.chat.id, message_id=call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('ptc_'))
    def handle_pitch_callback(call):
        val = float(call.data.replace('ptc_', ''))
        set_config(call.message.chat.id, 'pitch', val)
        bot.answer_callback_query(call.id, f"الحدة: {val:+.1f}")
        bot.edit_message_text(f"تم ضبط الحدة: {val:+.1f}.", chat_id=call.message.chat.id, message_id=call.message.message_id)

    # Instant Voice Cloning Handler: Receives Voice Note or Audio File
    @bot.message_handler(content_types=['voice', 'audio', 'document'])
    def handle_voice_upload(message):
        chat_id = message.chat.id
        file_id = None
        if message.voice:
            file_id = message.voice.file_id
        elif message.audio:
            file_id = message.audio.file_id
        elif message.document:
            fname = getattr(message.document, 'file_name', '') or ''
            if any(fname.lower().endswith(ext) for ext in ['.wav', '.mp3', '.ogg', '.oga', '.m4a', '.flac']):
                file_id = message.document.file_id

        if not file_id:
            bot.reply_to(message, "يرجى إرسال ملف صوتي أو تسجيل صوتي صالح.")
            return

        try:
            bot.send_chat_action(chat_id, 'record_voice')
            file_info = bot.get_file(file_id)
            downloaded = bot.download_file(file_info.file_path)

            ext = os.path.splitext(file_info.file_path)[1] or ".oga"
            temp_in = f"input_voice_{chat_id}_{int(time.time()*1000)}{ext}"
            with open(temp_in, "wb") as f:
                f.write(downloaded)

            eng = get_engine()
            emb = eng.extract_speaker_embedding(temp_in)

            user_custom_embeddings[chat_id] = emb
            set_config(chat_id, 'speaker', 'cloned')

            if os.path.exists(temp_in):
                os.remove(temp_in)

            bot.reply_to(message, "تم استنساخ الصوت بنجاح واعتماده كصوتك الحالي. أرسل أي نص الآن للتحدث به.")
        except Exception as e:
            print(f"[Bot] Clone error: {e}", flush=True)
            bot.reply_to(message, f"خطأ في استنساخ الصوت: {str(e)}")

    @bot.message_handler(func=lambda message: True)
    def handle_text_message(message):
        text = message.text.strip()
        if not text:
            return

        chat_id = message.chat.id
        cfg = get_config(chat_id)
        if cfg['speaker'] == 'cloned':
            spk_emb = user_custom_embeddings.get(chat_id, DEFAULT_CLONED_EMB)
        else:
            spk_emb = None

        try:
            bot.send_chat_action(chat_id, 'record_voice')
        except Exception:
            pass

        try:
            eng = get_engine()
            temp_wav = f"voice_{chat_id}_{int(time.time()*1000)}.wav"
            eng.synthesize(
                text,
                locale=cfg['locale'],
                speaker=cfg['speaker'],
                speaker_embedding=spk_emb,
                speed=cfg['speed'],
                pitch=cfg['pitch'],
                cf_guidance=cfg['cf_guidance'],
                temperature=cfg['temperature'],
                max_frames=192,
                out_wav=temp_wav
            )

            with open(temp_wav, "rb") as audio:
                try:
                    bot.send_voice(chat_id, audio, reply_to_message_id=message.message_id)
                except Exception:
                    audio.seek(0)
                    bot.send_audio(chat_id, audio, reply_to_message_id=message.message_id)

            if os.path.exists(temp_wav):
                os.remove(temp_wav)
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
