# VoiceLM Multilingual Text-to-Speech (TTS) on CPU & Kaggle

تشغيل نموذج **VoiceLM** لتوليد الكلام عالي الدقة بشكل مستقل على معالجات **CPU** وبدون الحاجة إلى كروت شاشة GPU، مع دعم 52 لغة و 416 صوتاً، وبوت تيليجرام تفاعلي متوافق بنسبة 100% مع بيئة **Kaggle**.

---

## المميزات الرئيسية
- **دعم 52 لغة عالمية**: العربية، الإنجليزية، الفرنسية، الألمانية، الإسبانية، الروسية، التركية، الصينية، اليابانية، الكورية، الهندية، وغيرها.
- **416 صوتاً مدمجاً**: 8 أصوات مميزة لكل لغة (4 ذكور و4 إناث).
- **التعرف التلقائي على اللغة**: يتعرف المحرك تلقائياً على لغة النص المدخل ويختار نبرة المتحدث المناسبة فورياً.
- **خفيف وسريع على CPU**: يعمل عبر محركات TensorFlow Lite / LiteRT الخفيفة ومحسن للعمل على أي سيرفر أو حاسوب محلي أو Kaggle Notebook.
- **توقف ذاتي ونهايات طبيعية**: يعتمد شرط الإيقاف الرسمي للمكتبة (`new_ids < 2`) لمنع الهلوسة والضوضاء بعد انتهاء الكلام.
- **معالجة النصوص المشكّلة وغير المشكّلة**: يدعم الحركات الإعرابية الكاملة وتطبيع الرموز الإملائية تلقائياً.
- **بوت تيليجرام مباشر وسريع**: واجهة نظيفة ومختصرة ترسل التسجيل الصوتي مباشرة، مع أوامر لاختيار الصوت `/voice` واللغة `/lang`.

---

## اللغات المدعومة (52 لغة)
العربية (`ar_xa`)، الإنجليزية (`en_us`, `en_gb`, `en_au`, `en_in`)، الفرنسية (`fr_fr`, `fr_ca`)، الإسبانية (`es_es`, `es_us`)، الألمانية (`de_de`)، الإيطالية (`it_it`)، الروسية (`ru_ru`)، التركية (`tr_tr`)، البرتغالية (`pt_br`)، الصينية (`cmn_cn`)، اليابانية (`ja_jp`)، الكورية (`ko_kr`)، الهندية (`hi_in`)، الأردية (`ur_pk`, `ur_in`)، الإندونيسية (`id_id`)، البولندية (`pl_pl`)، الأوكرانية (`uk_ua`)، الهولندية (`nl_nl`, `nl_be`)، السويدية (`sv_se`)، والمزيد.

---

## التثبيت السريع (Installation)

```bash
git clone https://github.com/shamsorachdi62/voicelm-arabic-tts.git
cd voicelm-arabic-tts
pip install -r requirements.txt
```

---

## الاستخدام عبر بايثون (Python API)

```python
from voicelm_engine import VoiceLMTTS

# تحميل المحرك
engine = VoiceLMTTS()

# توليد كلام من نص عربي (التعرف تلقائي أو محدد)
text = "بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِيمِ، أَهْلاً بِكُمْ فِي عَالَمِ التَّوْلِيدِ الصَّوْتِيِّ."
waveform = engine.synthesize(text, speaker="star04", out_wav="arabic.wav")

# توليد كلام بلغة أخرى (مثال إنجليزي)
text_en = "Hello and welcome to the multilingual VoiceLM speech generation system."
waveform_en = engine.synthesize(text_en, speaker="star04", out_wav="english.wav")
```

---

## تشغيل بوت تيليجرام (Telegram Bot)

1. احصل على التوكن من BotFather.
2. شغل البوت مباشرة:
```bash
python bot.py --token "YOUR_TELEGRAM_BOT_TOKEN"
```
أو عبر المتغير البيئي:
```bash
export BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
python bot.py
```

---

## التشغيل على كاجل (Kaggle CPU)

يمكنك تشغيل البوت على بيئة Kaggle CPU المجانية (4 أنوية، 30GB رام) باتباع الخطوات في ملف [kaggle_voicelm_bot.ipynb](kaggle_voicelm_bot.ipynb):

1. أنشئ نوت بوك جديد على Kaggle (واختر معالج CPU).
2. نفذ الخلايا بالتتابع:
   - تثبيت المتطلبات (`pip install -r requirements.txt`).
   - وضع توكن البوت في `BOT_TOKEN`.
   - تشغيل `python bot.py`.
3. سيبدأ البوت بالعمل فوراً ويستقبل رسائل المستخدمين على تيليجرام ويولد الصوت على خوادم كاجل.
