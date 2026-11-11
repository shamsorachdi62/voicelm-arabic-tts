import os
import sys
import re
import numpy as np
import scipy.io.wavfile as wavfile
import scipy.signal as signal

def phase_vocoder(audio, rate, sr=24000):
    """High-quality time-scale modification (speed change) using phase vocoder."""
    if abs(rate - 1.0) < 0.01 or len(audio) < 1000:
        return audio
    hop = 240
    nfft = 960
    f, t, D = signal.stft(audio, fs=sr, nperseg=nfft, noverlap=nfft - hop)
    time_steps = np.arange(0, D.shape[1], rate)
    time_steps = time_steps[time_steps < D.shape[1] - 1]
    if len(time_steps) == 0:
        return audio
        
    stretched_spec = np.zeros((D.shape[0], len(time_steps)), dtype=complex)
    stretched_spec[:, 0] = D[:, 0]
    phase_acc = np.angle(D[:, 0])
    omega = 2 * np.pi * np.arange(D.shape[0]) * hop / nfft
    
    for i, step in enumerate(time_steps[1:], 1):
        prev_idx = int(np.floor(step))
        next_idx = prev_idx + 1
        alpha = step - prev_idx
        
        mag = (1 - alpha) * np.abs(D[:, prev_idx]) + alpha * np.abs(D[:, next_idx])
        dphi = np.angle(D[:, next_idx]) - np.angle(D[:, prev_idx]) - omega
        dphi = dphi - 2 * np.pi * np.round(dphi / (2 * np.pi))
        phase_acc += omega + dphi
        stretched_spec[:, i] = mag * np.exp(1j * phase_acc)
        
    _, out = signal.istft(stretched_spec, fs=sr, nperseg=nfft, noverlap=nfft - hop)
    return out

def pitch_shift(audio, semitones, sr=24000):
    """Pitch shift in semitones (-6 to +6) preserving duration."""
    if abs(semitones) < 0.05 or len(audio) < 1000:
        return audio
    factor = 2.0 ** (semitones / 12.0)
    stretched = phase_vocoder(audio, factor, sr=sr)
    return signal.resample(stretched, len(audio))


# Cross-platform TFLite interpreter loader
def get_interpreter(model_path):
    try:
        from ai_edge_litert.interpreter import Interpreter
        return Interpreter(model_path=model_path)
    except ImportError:
        pass
    try:
        from tflite_runtime.interpreter import Interpreter
        return Interpreter(model_path=model_path)
    except ImportError:
        pass
    try:
        import tensorflow as tf
        return tf.lite.Interpreter(model_path=model_path)
    except ImportError:
        raise ImportError(
            "Could not find any TFLite runtime. Please install one of:\n"
            "  pip install ai-edge-litert\n"
            "or\n"
            "  pip install tflite-runtime\n"
            "or\n"
            "  pip install tensorflow"
        )

# Mapping constants reverse-engineered from speech::tts::SplitTfliteVoiceLmInferenceRunner
ENC_CA_MAP = {
    0: (24, 6), 1: (10, 16), 2: (11, 18), 3: (5, 2), 4: (1, 8), 5: (25, 7),
    6: (13, 3), 7: (0, 14), 8: (4, 17), 9: (9, 12), 10: (23, 20), 11: (22, 21),
}
TEMP_CA_IN = {
    0: (45, 14), 1: (23, 34), 2: (24, 36), 3: (13, 5), 4: (3, 16), 5: (46, 15),
    6: (27, 7), 7: (2, 30), 8: (12, 35), 9: (22, 25), 10: (44, 38), 11: (42, 39),
}
TEMP_SA_CYCLE = {
    0: (37, 16, 9, 3), 1: (40, 17, 48, 21), 2: (29, 13, 20, 8), 3: (11, 5, 51, 24),
    4: (43, 19, 18, 6), 5: (49, 22, 41, 18), 6: (31, 14, 21, 9), 7: (47, 20, 26, 10),
    8: (19, 7, 0, 0), 9: (4, 1, 28, 12), 10: (8, 2, 32, 15), 11: (50, 23, 10, 4),
}
SOUNDSTREAM_STATE_MAPPING = {
    237: 1, 236: 2, 134: 3, 141: 4, 148: 5, 155: 6, 163: 7, 170: 8,
    177: 9, 184: 10, 191: 11, 198: 12, 206: 13, 213: 14, 220: 15, 227: 16, 235: 17
}

SPEAKERS_INFO = {
    'star02': {'gender': 'female', 'desc': 'أنثوي فصيح'},
    'star04': {'gender': 'male',   'desc': 'ذكوري وقور'},
    'star05': {'gender': 'male',   'desc': 'ذكوري هادئ'},
    'star08': {'gender': 'female', 'desc': 'أنثوي دافئ'},
    'star11': {'gender': 'male',   'desc': 'ذكوري شاب'},
    'star12': {'gender': 'female', 'desc': 'أنثوي رزين'},
    'star13': {'gender': 'male',   'desc': 'ذكوري قوي'},
    'star16': {'gender': 'female', 'desc': 'أنثوي تعبيري'},
}

SUPPORTED_LOCALES = {
    'ar_xa': 'العربية', 'en_us': 'الإنجليزية (أمريكا)', 'en_gb': 'الإنجليزية (بريطانيا)',
    'fr_fr': 'الفرنسية', 'de_de': 'الألمانية', 'es_es': 'الإسبانية',
    'ru_ru': 'الروسية', 'tr_tr': 'التركية', 'it_it': 'الإيطالية',
    'ja_jp': 'اليابانية', 'cmn_cn': 'الصينية', 'ko_kr': 'الكورية',
    'hi_in': 'الهندية', 'ur_pk': 'الأردية', 'pt_br': 'البرتغالية',
    'id_id': 'الإندونيسية', 'fa_ir': 'الفارسية', 'nl_nl': 'الهولندية',
    'sv_se': 'السويدية', 'pl_pl': 'البولندية', 'uk_ua': 'الأوكرانية'
}

class MultilingualPromptStore:
    """Extracts all 416 speaker prompts across 52 languages from speaker_prompts.pb."""
    def __init__(self, pb_path):
        self.prompts = {}
        if not os.path.exists(pb_path):
            print(f"[PromptStore] Warning: {pb_path} not found.")
            return

        with open(pb_path, "rb") as f:
            d = f.read()

        loc_matches = list(re.finditer(rb"\b([a-z]{2,3}_[a-z]{2})\b", d))
        for idx, lm in enumerate(loc_matches):
            loc = lm.group().decode()
            start = lm.start()
            end = loc_matches[idx+1].start() if idx+1 < len(loc_matches) else len(d)
            block = d[start:end]

            for sm in re.finditer(rb"star\d{2}", block):
                spk = sm.group().decode()
                p_star = sm.start()
                p_tag4 = block.find(b"\x22", p_star, p_star + 100)
                if p_tag4 == -1:
                    continue

                p = p_tag4 + 1
                length = 0
                shift = 0
                while True:
                    b = block[p]
                    p += 1
                    length |= (b & 0x7F) << shift
                    if (b & 0x80) == 0:
                        break
                    shift += 7

                payload = block[p:p + length]
                num_floats = length // 4
                T = num_floats // 128
                if num_floats % 128 == 0 and T > 10:
                    floats = np.frombuffer(payload, dtype=np.float32).reshape(1, T, 128)
                    self.prompts[(loc, spk)] = floats

        print(f"[PromptStore] Loaded {len(self.prompts)} prompts across {len(loc_matches)} locales.", flush=True)

    def get(self, locale='ar_xa', speaker='star04'):
        if (locale, speaker) in self.prompts:
            return self.prompts[(locale, speaker)]
        # Try fallback in same locale
        for (l, s), p in self.prompts.items():
            if l == locale:
                return p
        # Global fallback to ar_xa star04
        if ('ar_xa', 'star04') in self.prompts:
            return self.prompts[('ar_xa', 'star04')]
        return None

class VoiceLMTTS:
    def __init__(self, models_dir=None):
        if models_dir is None:
            models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
        self.models_dir = models_dir
        
        print(f"[VoiceLM] Initializing models from {self.models_dir}...", flush=True)
        self.prep = get_interpreter(os.path.join(models_dir, "voicelm_preprocessing.tflite"))
        self.prep.allocate_tensors()
        
        self.enc = get_interpreter(os.path.join(models_dir, "voicelm_encoder.tflite"))
        self.enc.allocate_tensors()
        
        self.temp = get_interpreter(os.path.join(models_dir, "voicelm_temporal_decoder.tflite"))
        self.temp.allocate_tensors()
        
        self.depth = get_interpreter(os.path.join(models_dir, "voicelm_merged_depth_decoder.tflite"))
        self.depth.allocate_tensors()
        
        self.quant = get_interpreter(os.path.join(models_dir, "soundstream_quantizer.tflite"))
        self.quant.allocate_tensors()
        
        self.dec = get_interpreter(os.path.join(models_dir, "soundstream_decoder.tflite"))
        self.dec.allocate_tensors()
        
        # Load official iSTFT window
        win_path = os.path.join(models_dir, "istft_window_truediv.npy")
        self.istft_window = np.load(win_path)
        
        # Load full multilingual prompt store
        pb_path = os.path.join(models_dir, "speaker_prompts.pb")
        self.prompt_store = MultilingualPromptStore(pb_path)
        
        # SoundStream audio encoder for voice cloning (lazy loaded)
        self._soundstream_enc = None

    def get_soundstream_encoder(self):
        if self._soundstream_enc is None:
            enc_path = os.path.join(self.models_dir, "soundstream_encoder.tflite")
            if not os.path.exists(enc_path):
                raise FileNotFoundError(f"soundstream_encoder.tflite not found at {enc_path}")
            self._soundstream_enc = get_interpreter(enc_path)
            self._soundstream_enc.allocate_tensors()
            
            inps = self._soundstream_enc.get_input_details()
            outs = self._soundstream_enc.get_output_details()
            self._enc_audio_idx = [i['index'] for i in inps if i['name'] == 'input_audio'][0]
            self._enc_bottleneck_idx = [o['index'] for o in outs if 'bottleneck' in o['name']][0]
            
            self._enc_state_pairs = {}
            for inp in inps:
                if inp['name'] == 'input_audio':
                    continue
                inp_name_core = inp['name'].split('/')[1]
                for out in outs:
                    if 'bottleneck' in out['name']:
                        continue
                    out_name_core = out['name'].split('/')[1]
                    if inp_name_core == out_name_core and tuple(inp['shape']) == tuple(out['shape']):
                        self._enc_state_pairs[inp['index']] = out['index']
                        break
        return self._soundstream_enc

    def extract_speaker_embedding(self, audio_source, max_frames=80):
        """
        Extracts 128-dimensional speaker embedding from any audio file (wav, oga, mp3, ogg, etc.)
        or numpy array. Returns numpy array of shape [1, T, 128].
        """
        if isinstance(audio_source, str):
            try:
                import soundfile as sf
                audio, sr = sf.read(audio_source)
            except Exception:
                sr, audio = wavfile.read(audio_source)
        elif isinstance(audio_source, tuple):
            sr, audio = audio_source
        else:
            sr, audio = 24000, audio_source

        if audio.ndim > 1:
            audio = audio[:, 0]
        if sr != 24000:
            import scipy.signal as signal
            audio = signal.resample(audio, int(len(audio) * 24000 / sr))
        audio = audio.astype(np.float32)
        max_abs = np.abs(audio).max()
        if max_abs > 1.0:
            audio = audio / max_abs
        elif max_abs > 1e-4:
            audio = audio / max_abs

        enc = self.get_soundstream_encoder()
        inps = enc.get_input_details()
        window = np.hanning(480).astype(np.float32)
        states = {i['index']: np.zeros(i['shape'], dtype=np.float32) for i in inps if i['name'] != 'input_audio'}

        num_chunks = min(len(audio) // 2400, max_frames)
        if num_chunks < 5:
            num_chunks = max(1, len(audio) // 2400)

        vecs = []
        for c in range(num_chunks):
            stft_10 = np.zeros((1, 10, 240, 2), dtype=np.float32)
            for s in range(10):
                start = c * 2400 + s * 240
                f = audio[start : start + 480]
                if len(f) < 480:
                    f = np.pad(f, (0, 480 - len(f)))
                spec = np.fft.rfft(f * window, n=480)
                stft_10[0, s, :, 0] = spec[:240].real
                stft_10[0, s, :, 1] = spec[:240].imag
            enc.set_tensor(self._enc_audio_idx, stft_10)
            for in_idx, s_val in states.items():
                enc.set_tensor(in_idx, s_val)
            enc.invoke()
            vecs.append(enc.get_tensor(self._enc_bottleneck_idx))
            for in_idx, out_idx in self._enc_state_pairs.items():
                states[in_idx] = enc.get_tensor(out_idx)

        return np.concatenate(vecs, axis=1)

    def detect_locale(self, text):
        """Auto-detects language script and returns matching locale code."""
        # 1. Non-Latin scripts by Unicode range:
        if re.search(r'[\u067E\u0686\u0698\u06AF\u06BA\u06BE]', text): # Urdu specific letters
            return 'ur_pk'
        if re.search(r'[\u0600-\u06FF]', text): # Arabic
            return 'ar_xa'
        if re.search(r'[\u0400-\u04FF]', text): # Cyrillic
            if re.search(r'[іїєґ]', text, re.IGNORECASE):
                return 'uk_ua'
            return 'ru_ru'
        if re.search(r'[\u3040-\u30FF]', text): # Japanese Kana
            return 'ja_jp'
        if re.search(r'[\uAC00-\uD7AF]', text): # Korean Hangul
            return 'ko_kr'
        if re.search(r'[\u4E00-\u9FFF]', text): # Chinese Ideographs
            return 'cmn_cn'
        if re.search(r'[\u0590-\u05FF]', text): # Hebrew
            return 'he_il'
        if re.search(r'[\u0370-\u03FF]', text): # Greek
            return 'el_gr'
        if re.search(r'[\u0900-\u097F]', text): # Hindi (Devanagari)
            return 'hi_in'
        if re.search(r'[\u0980-\u09FF]', text): # Bengali
            return 'bn_in'
        if re.search(r'[\u0B80-\u0BFF]', text): # Tamil
            return 'ta_in'
        if re.search(r'[\u0C00-\u0C7F]', text): # Telugu
            return 'te_in'
        if re.search(r'[\u0C80-\u0CFF]', text): # Kannada
            return 'kn_in'
        if re.search(r'[\u0D00-\u0D7F]', text): # Malayalam
            return 'ml_in'
        if re.search(r'[\u0A80-\u0AFF]', text): # Gujarati
            return 'gu_in'
        if re.search(r'[\u0E00-\u0E7F]', text): # Thai
            return 'th_th'

        # 2. Latin script character markers:
        # Turkish
        if re.search(r'[ğışIİ]', text):
            return 'tr_tr'
        # Vietnamese
        if re.search(r'[đĐơưƠƯ]', text):
            return 'vi_vn'
        # German
        if re.search(r'[äöüßÄÖÜ]', text):
            return 'de_de'
        # French
        if re.search(r'[éèêëàâîïôûùçœÉÈÊÀÂÔÛÇ]', text):
            return 'fr_fr'
        # Spanish
        if re.search(r'[ñáíóú¿¡ÑÁÍÓÚ]', text):
            return 'es_es'
        # Portuguese
        if re.search(r'[ãõÃÕ]', text):
            return 'pt_br'
        # Polish
        if re.search(r'[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]', text):
            return 'pl_pl'

        # Default Latin: English (en_us)
        return 'en_us'

    def normalize_text(self, text):
        text = re.sub(r'[\u0670]', '', text)       # Dagger alif -> canonical MSA spelling
        text = re.sub(r'[\u06D6-\u06ED]', '', text) # Recitation marks
        return text.strip()

    def _stream_istft(self, stft_frames):
        num_frames = stft_frames.shape[0]
        out_samples = []
        state = np.zeros(480, dtype=np.float32)
        for i in range(num_frames):
            spec_240 = stft_frames[i]
            spec_241 = np.pad(spec_240, ((0, 1), (0, 0)), mode='constant')
            c_spec = spec_241[:, 0] + 1j * spec_241[:, 1]
            time_frame = np.fft.irfft(c_spec, n=480).astype(np.float32)
            win_frame = time_frame * self.istft_window
            state += win_frame
            out_samples.append(state[:240].copy())
            state[:240] = state[240:]
            state[240:] = 0.0
        out_samples.append(state[:240].copy())
        return np.concatenate(out_samples)

    def _synthesize_chunk(self, chunk_text, locale='ar_xa', speaker='star04', speaker_embedding=None, max_frames=192, cf_guidance=2.2, temperature=0.4, seed=None):
        if seed is not None:
            np.random.seed(int(seed))
        if speaker_embedding is not None:
            prompt_floats = speaker_embedding
        else:
            prompt_floats = self.prompt_store.get(locale=locale, speaker=speaker)
        if prompt_floats is None:
            prompt_floats = np.zeros((1, 54, 128), dtype=np.float32)

        chunk_text = self.normalize_text(chunk_text)
        text_bytes = list(chunk_text.encode('utf-8'))
        t_len = min(len(text_bytes), 256)

        text_array = np.zeros((1, 256), dtype=np.int32)
        text_array[0, :t_len] = text_bytes[:t_len]
        text_size = np.array([t_len], dtype=np.int32)

        prompt_array = np.zeros((1, 128, 128), dtype=np.float32)
        p_len = min(prompt_floats.shape[1], 128)
        prompt_array[0, :p_len, :] = prompt_floats[0, :p_len, :]
        prompt_size = np.array([p_len], dtype=np.int32)

        audio_ctx = np.zeros((1, 128, 128), dtype=np.float32)
        audio_ctx_size = np.array([0], dtype=np.int32)

        self.prep.set_tensor(3, text_array)
        self.prep.set_tensor(4, text_size)
        self.prep.set_tensor(0, prompt_array)
        self.prep.set_tensor(5, prompt_size)
        self.prep.set_tensor(1, audio_ctx)
        self.prep.set_tensor(2, audio_ctx_size)
        self.prep.invoke()

        self.enc.set_tensor(0, self.prep.get_tensor(48))
        self.enc.set_tensor(1, self.prep.get_tensor(0))
        self.enc.set_tensor(2, self.prep.get_tensor(1))
        self.enc.set_tensor(3, self.prep.get_tensor(52))
        self.enc.set_tensor(4, self.prep.get_tensor(46))
        self.enc.set_tensor(5, self.prep.get_tensor(56))
        self.enc.invoke()

        enc_outs = self.enc.get_output_details()
        enc_paddings = self.enc.get_tensor(enc_outs[15]['index'])
        target_emb = self.enc.get_tensor(enc_outs[19]['index'])

        self.temp.set_tensor(33, enc_paddings)
        for layer in range(12):
            k_out_idx, v_out_idx = ENC_CA_MAP[layer]
            k_in_idx, v_in_idx = TEMP_CA_IN[layer]
            self.temp.set_tensor(k_in_idx, self.enc.get_tensor(enc_outs[k_out_idx]['index']))
            self.temp.set_tensor(v_in_idx, self.enc.get_tensor(enc_outs[v_out_idx]['index']))

        sa_cache = {}
        for layer in range(12):
            sa_cache[(layer, 'key')] = np.zeros((2, 193, 128), dtype=np.float32)
            sa_cache[(layer, 'value')] = np.zeros((2, 193, 128), dtype=np.float32)

        dec_inputs = self.dec.get_input_details()
        dec_state = {inp['index']: np.zeros(inp['shape'], dtype=inp['dtype']) for inp in dec_inputs if inp['name'] != 'input_audio'}
        audio_inp_idx = [i['index'] for i in dec_inputs if i['name'] == 'input_audio'][0]

        quant_inps = self.quant.get_input_details()
        quant_outs = self.quant.get_output_details()
        temp_outs = self.temp.get_output_details()
        depth_outs = self.depth.get_output_details()

        stft_frames_list = []

        for t in range(max_frames):
            mask = np.full((1, 1, 193), -3.4028235e+38, dtype=np.float32)
            mask[0, 0, :t+1] = 0.0

            self.temp.set_tensor(1, np.array(t, dtype=np.int32))
            self.temp.set_tensor(6, target_emb)
            self.temp.set_tensor(17, mask)

            for layer in range(12):
                k_in, _, v_in, _ = TEMP_SA_CYCLE[layer]
                self.temp.set_tensor(k_in, sa_cache[(layer, 'key')])
                self.temp.set_tensor(v_in, sa_cache[(layer, 'value')])

            self.temp.invoke()

            for layer in range(12):
                _, k_out, _, v_out = TEMP_SA_CYCLE[layer]
                sa_cache[(layer, 'key')] = self.temp.get_tensor(temp_outs[k_out]['index'])
                sa_cache[(layer, 'value')] = self.temp.get_tensor(temp_outs[v_out]['index'])

            temporal_output = self.temp.get_tensor(temp_outs[11]['index'])

            u = np.random.uniform(1e-6, 1.0 - 1e-6, size=(1, 18, 40)).astype(np.float32)
            noise = -np.log(-np.log(u))

            self.depth.set_tensor(0, np.array([cf_guidance], dtype=np.float32))
            self.depth.set_tensor(1, temporal_output)
            self.depth.set_tensor(2, noise)
            self.depth.set_tensor(3, np.array([temperature], dtype=np.float32))
            self.depth.invoke()

            ss_tokens = self.depth.get_tensor(depth_outs[0]['index'])
            target_emb = self.depth.get_tensor(depth_outs[1]['index'])
            new_ids = self.depth.get_tensor(depth_outs[2]['index'])

            if new_ids < 2 and t >= 3:
                break

            self.quant.set_tensor(quant_inps[0]['index'], ss_tokens.reshape(1, 18))
            self.quant.invoke()
            audio_emb_128 = self.quant.get_tensor(quant_outs[0]['index'])

            self.dec.set_tensor(audio_inp_idx, audio_emb_128.reshape(1, 1, 128))
            for in_idx, s_val in dec_state.items():
                self.dec.set_tensor(in_idx, s_val)
            self.dec.invoke()

            stft_chunk = self.dec.get_tensor(234)
            for step in range(10):
                stft_frames_list.append(stft_chunk[0, step])

            for out_idx, in_idx in SOUNDSTREAM_STATE_MAPPING.items():
                dec_state[in_idx] = self.dec.get_tensor(out_idx)

        if len(stft_frames_list) == 0:
            return np.zeros(2400, dtype=np.float32)

        stft_all = np.array(stft_frames_list)
        return self._stream_istft(stft_all)

    def split_into_chunks(self, text, max_bytes=170):
        """
        Hierarchical text chunking ensuring every chunk is <= max_bytes (<= 256 byte input limit),
        splitting first by sentence punctuation, then by clauses, and finally by words.
        """
        text = self.normalize_text(text)
        if not text:
            return []
        if len(text.encode('utf-8')) <= max_bytes:
            return [text]

        # Level 1: Sentence boundaries
        major_delims = r'([.!?؛؟\n]+)'
        segments = re.split(major_delims, text)
        
        rebuilt = []
        curr = ""
        for seg in segments:
            if not seg:
                continue
            cand = (curr + seg).strip()
            if len(cand.encode('utf-8')) <= max_bytes:
                curr = cand
            else:
                if curr:
                    rebuilt.append(curr)
                curr = seg.strip()
        if curr:
            rebuilt.append(curr)

        # Level 2: Sub-clause boundaries (commas, colons, dashes)
        final_chunks = []
        for chunk in rebuilt:
            if len(chunk.encode('utf-8')) <= max_bytes:
                final_chunks.append(chunk)
                continue
            
            subparts = re.split(r'([،,:-]+)', chunk)
            sub_curr = ""
            for sub in subparts:
                if not sub:
                    continue
                cand = (sub_curr + sub).strip()
                if len(cand.encode('utf-8')) <= max_bytes:
                    sub_curr = cand
                else:
                    if sub_curr:
                        final_chunks.append(sub_curr)
                    sub_curr = sub.strip()
            if sub_curr:
                final_chunks.append(sub_curr)

        # Level 3: Word boundaries (space-separated)
        safe_chunks = []
        for chunk in final_chunks:
            if len(chunk.encode('utf-8')) <= max_bytes:
                safe_chunks.append(chunk)
                continue
            words = chunk.split()
            w_curr = ""
            for w in words:
                cand = (w_curr + " " + w).strip()
                if len(cand.encode('utf-8')) <= max_bytes:
                    w_curr = cand
                else:
                    if w_curr:
                        safe_chunks.append(w_curr)
                    w_curr = w
            if w_curr:
                safe_chunks.append(w_curr)

        return safe_chunks if safe_chunks else [text]

    def synthesize(self, text, locale=None, speaker='star04', speaker_embedding=None, speed=1.0, pitch=0.0, cf_guidance=2.2, temperature=0.4, seed=None, volume=1.0, max_frames=192, out_wav=None):
        """
        Multilingual synthesis with full acoustic and neural parameter control:
        - locale: Language/dialect code (ar_xa, en_us, fr_fr, etc.) or None for auto-detect
        - speaker: Voice profile (star02, star04, star05, star08, star11, star12, star13, star16)
        - speaker_embedding: Optional custom cloned speaker embedding [1, T, 128]
        - speed: Playback tempo rate (0.5 to 2.0, default 1.0)
        - pitch: Pitch shift in semitones (-6 to +6, default 0.0)
        - cf_guidance: Classifier-free guidance scale (1.0 to 5.0, default 2.2)
        - temperature: Sampling temperature (0.1 to 1.0, default 0.4)
        - seed: Random seed for reproducible intonation
        - volume: Output volume scaling (0.1 to 1.5, default 1.0)
        """
        if locale is None:
            locale = self.detect_locale(text)

        chunks = self.split_into_chunks(text)
        waveforms = []
        silence = np.zeros(int(24000 * 0.15), dtype=np.float32)

        for idx, chunk in enumerate(chunks):
            w = self._synthesize_chunk(
                chunk,
                locale=locale,
                speaker=speaker,
                speaker_embedding=speaker_embedding,
                max_frames=max_frames,
                cf_guidance=cf_guidance,
                temperature=temperature,
                seed=seed
            )
            waveforms.append(w)
            if idx < len(chunks) - 1:
                waveforms.append(silence)

        waveform = np.concatenate(waveforms)

        # Apply pitch shifting if specified
        if abs(pitch) >= 0.05:
            waveform = pitch_shift(waveform, pitch, sr=24000)

        # Apply time-scale modification (speed) if specified
        if abs(speed - 1.0) >= 0.02:
            waveform = phase_vocoder(waveform, speed, sr=24000)

        # Apply volume and peak normalization
        max_val = np.abs(waveform).max()
        if max_val > 1e-4:
            gain = min(max(volume, 0.1), 1.5)
            waveform = (waveform / max_val) * gain * 0.95

        if out_wav:
            wavfile.write(out_wav, 24000, (waveform * 32767).astype(np.int16))
        return waveform
