"""
Empathy Engine - Emotionally Intelligent Text-to-Speech Service
"""

import os
import uuid
import math
import json
import struct
import wave
import subprocess
import tempfile
from flask import Flask, request, jsonify, send_file, render_template, send_from_directory

app = Flask(__name__)
AUDIO_DIR = os.path.join("static", "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# EMOTION DETECTION ENGINE
# ---------------------------------------------------------------------------

# Emotion lexicon: word → (emotion, weight)
EMOTION_LEXICON = {
    # Joy / Happy
    "amazing": ("joy", 2.0), "awesome": ("joy", 2.0), "fantastic": ("joy", 2.0),
    "wonderful": ("joy", 1.8), "excellent": ("joy", 1.8), "great": ("joy", 1.5),
    "good": ("joy", 1.0), "happy": ("joy", 1.8), "love": ("joy", 1.5),
    "best": ("joy", 1.8), "brilliant": ("joy", 2.0), "perfect": ("joy", 1.8),
    "excited": ("joy", 2.0), "thrilled": ("joy", 2.2), "delighted": ("joy", 1.8),
    "hooray": ("joy", 2.5), "yay": ("joy", 2.0), "celebrate": ("joy", 1.8),
    "glad": ("joy", 1.2), "pleased": ("joy", 1.2), "overjoyed": ("joy", 2.5),

    # Sadness
    "sad": ("sadness", 1.5), "terrible": ("sadness", 2.0), "awful": ("sadness", 2.0),
    "horrible": ("sadness", 2.0), "bad": ("sadness", 1.0), "unfortunate": ("sadness", 1.5),
    "sorry": ("sadness", 1.2), "regret": ("sadness", 1.5), "miss": ("sadness", 1.2),
    "loss": ("sadness", 1.8), "heartbroken": ("sadness", 2.5), "devastated": ("sadness", 2.5),
    "depressed": ("sadness", 2.0), "miserable": ("sadness", 2.2), "crying": ("sadness", 2.0),
    "grief": ("sadness", 2.2), "mourn": ("sadness", 2.0),

    # Anger / Frustrated
    "angry": ("anger", 2.0), "furious": ("anger", 2.5), "frustrated": ("anger", 1.8),
    "annoyed": ("anger", 1.5), "hate": ("anger", 2.0), "terrible": ("anger", 1.5),
    "ridiculous": ("anger", 1.8), "outrageous": ("anger", 2.0), "unacceptable": ("anger", 1.8),
    "worst": ("anger", 2.0), "disgusting": ("anger", 2.2), "infuriating": ("anger", 2.5),
    "rage": ("anger", 2.5), "livid": ("anger", 2.5),

    # Fear / Concern
    "worried": ("fear", 1.5), "scared": ("fear", 2.0), "afraid": ("fear", 1.8),
    "anxious": ("fear", 1.5), "concerned": ("fear", 1.2), "nervous": ("fear", 1.5),
    "terrified": ("fear", 2.5), "panicking": ("fear", 2.5), "dread": ("fear", 2.0),
    "fear": ("fear", 2.0), "frightened": ("fear", 2.0), "alarmed": ("fear", 1.8),
    "horrified": ("fear", 2.5),

    # Surprise
    "wow": ("surprise", 2.0), "surprising": ("surprise", 1.8), "shocked": ("surprise", 2.0),
    "unexpected": ("surprise", 1.5), "unbelievable": ("surprise", 2.0),
    "incredible": ("surprise", 2.0), "astonishing": ("surprise", 2.0),
    "remarkable": ("surprise", 1.5), "astounding": ("surprise", 2.2),
    "whoa": ("surprise", 2.0), "omg": ("surprise", 2.5),

    # Inquisitive
    "why": ("inquisitive", 1.0), "how": ("inquisitive", 0.8), "what": ("inquisitive", 0.8),
    "wondering": ("inquisitive", 1.5), "curious": ("inquisitive", 1.5),
    "question": ("inquisitive", 1.2), "understand": ("inquisitive", 1.0),
    "explain": ("inquisitive", 1.2), "clarify": ("inquisitive", 1.2),
    "confused": ("inquisitive", 1.5), "unsure": ("inquisitive", 1.2),
}

# Intensifiers and negators
INTENSIFIERS = {"very", "extremely", "incredibly", "absolutely", "so", "really", "truly", "deeply", "utterly"}
NEGATORS = {"not", "no", "never", "neither", "nor", "nothing", "nowhere", "nobody", "none", "hardly", "barely"}


def detect_emotion(text: str) -> dict:
    """
    Analyze text and return emotion with intensity score (0.0–1.0).
    Returns: {emotion, intensity, scores, exclamation_count, question_count, caps_ratio}
    """
    words = text.lower().split()
    tokens = []
    i = 0
    while i < len(words):
        word = ''.join(c for c in words[i] if c.isalpha())
        tokens.append(word)
        i += 1

    scores = {
        "joy": 0.0, "sadness": 0.0, "anger": 0.0,
        "fear": 0.0, "surprise": 0.0, "inquisitive": 0.0, "neutral": 0.3
    }

    # Scan tokens with context window
    for idx, token in enumerate(tokens):
        if token in EMOTION_LEXICON:
            emotion, weight = EMOTION_LEXICON[token]
            # Check for intensifier before this word
            if idx > 0 and tokens[idx - 1] in INTENSIFIERS:
                weight *= 1.5
            # Check for negator
            negated = False
            for j in range(max(0, idx - 3), idx):
                if tokens[j] in NEGATORS:
                    negated = True
                    break
            if negated:
                # Flip to opposite emotion on negation
                opposite = {"joy": "sadness", "sadness": "joy", "anger": "fear",
                            "fear": "anger", "surprise": "neutral", "inquisitive": "neutral"}
                opp = opposite.get(emotion, "neutral")
                scores[opp] += weight * 0.7
            else:
                scores[emotion] += weight

    # Structural signals
    exclamation_count = text.count('!')
    question_count = text.count('?')
    caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)

    # Boost scores from structural signals
    scores["joy"] += exclamation_count * 0.4
    scores["surprise"] += exclamation_count * 0.3
    scores["inquisitive"] += question_count * 0.8
    if caps_ratio > 0.3:
        scores["anger"] += 1.0
        scores["surprise"] += 0.5

    # Determine winner
    dominant_emotion = max(scores, key=scores.get)
    dominant_score = scores[dominant_emotion]

    # Compute intensity (0.0–1.0) — clamp at 3.0 max raw
    raw_intensity = min(dominant_score / 3.0, 1.0)
    # Ensure minimum intensity for non-neutral emotions
    if dominant_emotion != "neutral" and raw_intensity < 0.2:
        raw_intensity = 0.2

    return {
        "emotion": dominant_emotion,
        "intensity": round(raw_intensity, 3),
        "scores": {k: round(v, 3) for k, v in scores.items()},
        "exclamation_count": exclamation_count,
        "question_count": question_count,
        "caps_ratio": round(caps_ratio, 3),
    }


# ---------------------------------------------------------------------------
# VOICE PARAMETER MAPPING
# ---------------------------------------------------------------------------

# Base profile per emotion: (rate_factor, pitch_semitones, volume_factor)
# rate_factor: 1.0 = normal, >1 = faster, <1 = slower
# pitch_semitones: shift in semitones from base pitch
# volume_factor: 1.0 = normal
EMOTION_BASE_PROFILES = {
    "joy":        {"rate": 1.20, "pitch_st": +3.0, "volume": 1.10},
    "sadness":    {"rate": 0.80, "pitch_st": -2.5, "volume": 0.85},
    "anger":      {"rate": 1.30, "pitch_st": +1.5, "volume": 1.25},
    "fear":       {"rate": 1.15, "pitch_st": +1.0, "volume": 0.90},
    "surprise":   {"rate": 1.25, "pitch_st": +4.0, "volume": 1.15},
    "inquisitive": {"rate": 0.95, "pitch_st": +1.5, "volume": 0.95},
    "neutral":    {"rate": 1.00, "pitch_st":  0.0, "volume": 1.00},
}


def get_voice_params(emotion: str, intensity: float) -> dict:
    """
    Interpolate between neutral and the emotion's base profile using intensity.
    Returns rate, pitch_st, volume, and a human-readable description.
    """
    base = EMOTION_BASE_PROFILES.get(emotion, EMOTION_BASE_PROFILES["neutral"])
    neutral = EMOTION_BASE_PROFILES["neutral"]

    rate   = neutral["rate"]   + (base["rate"]     - neutral["rate"])   * intensity
    pitch  = neutral["pitch_st"] + (base["pitch_st"] - neutral["pitch_st"]) * intensity
    volume = neutral["volume"] + (base["volume"]   - neutral["volume"]) * intensity

    descriptions = {
        "joy":        "Upbeat and enthusiastic",
        "sadness":    "Soft and subdued",
        "anger":      "Firm and forceful",
        "fear":       "Tense and cautious",
        "surprise":   "High and animated",
        "inquisitive": "Measured and curious",
        "neutral":    "Calm and balanced",
    }

    return {
        "rate": round(rate, 3),
        "pitch_st": round(pitch, 3),
        "volume": round(volume, 3),
        "description": descriptions.get(emotion, "Balanced"),
    }


# ---------------------------------------------------------------------------
# AUDIO SYNTHESIS (pure Python WAV → pyttsx3-style sine TTS stub)
# Uses espeak if available, else generates a clearly labelled tone wav
# ---------------------------------------------------------------------------

def semitones_to_ratio(semitones: float) -> float:
    return 2 ** (semitones / 12.0)


def synthesize_speech(text: str, voice_params: dict, output_path: str) -> bool:
    """
    Try espeak first (if installed), fall back to gTTS, fall back to tone wav.
    Applies pitch and rate via sox or ffmpeg if available.
    Returns True on success.
    """
    rate = voice_params["rate"]
    pitch_st = voice_params["pitch_st"]
    volume = voice_params["volume"]

    # --- Attempt 1: espeak + sox pipeline ---
    try:
        espeak_ok = subprocess.run(["which", "espeak"], capture_output=True).returncode == 0
        sox_ok    = subprocess.run(["which", "sox"],    capture_output=True).returncode == 0
        ffmpeg_ok = subprocess.run(["which", "ffmpeg"], capture_output=True).returncode == 0

        if espeak_ok:
            # espeak rate is words per minute (default ~175)
            wpm = int(175 * rate)
            wpm = max(80, min(wpm, 400))

            # espeak pitch is 0-99, default 50; map semitone shift
            pitch_val = int(50 + pitch_st * 4)
            pitch_val = max(0, min(99, pitch_val))

            # espeak amplitude 0-200, default 100
            amp = int(100 * volume)
            amp = max(10, min(200, amp))

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name

            cmd = [
                "espeak", "-v", "en-us",
                "-s", str(wpm),
                "-p", str(pitch_val),
                "-a", str(amp),
                "-w", tmp_path,
                text
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            if result.returncode == 0 and os.path.exists(tmp_path):
                # convert to proper wav
                if ffmpeg_ok:
                    subprocess.run([
                        "ffmpeg", "-y", "-i", tmp_path,
                        "-ar", "22050", "-ac", "1",
                        output_path
                    ], capture_output=True, timeout=30)
                    os.unlink(tmp_path)
                else:
                    import shutil
                    shutil.move(tmp_path, output_path)
                return True
    except Exception as e:
        print(f"espeak attempt failed: {e}")

    # --- Attempt 2: gTTS ---
    try:
        from gtts import gTTS
        slow = rate < 0.85
        tts = gTTS(text=text, lang='en', slow=slow)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_mp3 = tmp.name
        tts.save(tmp_mp3)

        # Convert to wav with ffmpeg if available
        ffmpeg_ok = subprocess.run(["which", "ffmpeg"], capture_output=True).returncode == 0
        if ffmpeg_ok:
            # Apply pitch shift and tempo change via ffmpeg
            pitch_ratio = semitones_to_ratio(pitch_st)
            atempo = max(0.5, min(2.0, rate))

            filters = []
            if abs(pitch_st) > 0.1:
                # asetrate trick: shift pitch then restore sample rate
                filters.append(f"asetrate=22050*{pitch_ratio:.4f},aresample=22050")
            if abs(rate - 1.0) > 0.05:
                filters.append(f"atempo={atempo:.3f}")
            if abs(volume - 1.0) > 0.05:
                filters.append(f"volume={volume:.3f}")

            filter_str = ",".join(filters) if filters else "anull"
            subprocess.run([
                "ffmpeg", "-y", "-i", tmp_mp3,
                "-af", filter_str,
                "-ar", "22050",
                output_path
            ], capture_output=True, timeout=30)
        else:
            import shutil
            shutil.move(tmp_mp3, output_path)

        os.unlink(tmp_mp3)
        return True
    except Exception as e:
        print(f"gTTS attempt failed: {e}")

    # --- Attempt 3: pyttsx3 ---
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty('rate', int(200 * rate))
        engine.setProperty('volume', min(1.0, volume))
        engine.save_to_file(text, output_path)
        engine.runAndWait()
        if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
            return True
    except Exception as e:
        print(f"pyttsx3 attempt failed: {e}")

    # --- Fallback: generate a descriptive tone WAV ---
    _generate_tone_wav(text, voice_params, output_path)
    return True


def _generate_tone_wav(text: str, voice_params: dict, output_path: str):
    """Generate a simple multi-tone WAV to indicate the emotion profile (demo fallback)."""
    sample_rate = 22050
    duration = max(1.5, len(text) * 0.06)  # scale with text length
    num_samples = int(sample_rate * duration)

    # Base frequency modulated by pitch
    base_freq = 220.0 * semitones_to_ratio(voice_params["pitch_st"])
    volume = voice_params["volume"]
    rate = voice_params["rate"]

    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        # Add vibrato to make it feel more expressive
        vibrato = 1 + 0.02 * math.sin(2 * math.pi * 5.5 * t * rate)
        freq = base_freq * vibrato
        # Envelope: quick attack, sustain, release
        envelope = min(1.0, t * 10) * min(1.0, (duration - t) * 5)
        sample = envelope * volume * math.sin(2 * math.pi * freq * t)
        # Add a harmonic for richness
        sample += 0.3 * envelope * volume * math.sin(2 * math.pi * freq * 2 * t)
        samples.append(int(sample * 16000))

    with wave.open(output_path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f'<{len(samples)}h', *samples))


# ---------------------------------------------------------------------------
# SSML GENERATOR (bonus)
# ---------------------------------------------------------------------------

def generate_ssml(text: str, emotion: str, intensity: float, voice_params: dict) -> str:
    """Generate SSML markup for the text based on emotion."""
    rate_pct  = int(voice_params["rate"] * 100)
    pitch_pct = int(voice_params["pitch_st"] * 5)  # approximate %
    vol_pct   = int(voice_params["volume"] * 100)

    pitch_str  = f"+{pitch_pct}%" if pitch_pct >= 0 else f"{pitch_pct}%"
    vol_str    = f"+{vol_pct - 100}%" if vol_pct >= 100 else f"{vol_pct - 100}%"

    ssml = f"""<speak>
  <prosody rate="{rate_pct}%" pitch="{pitch_str}" volume="{vol_str}">
    {text}
  </prosody>
</speak>"""
    return ssml


# ---------------------------------------------------------------------------
# FLASK ROUTES
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/static/audio/<path:filename>")
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename)


@app.route("/analyze", methods=["POST"])
def analyze():
    """Analyze emotion without generating audio (for live preview)."""
    data = request.get_json(force=True)
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400

    emotion_data = detect_emotion(text)
    voice_params  = get_voice_params(emotion_data["emotion"], emotion_data["intensity"])

    return jsonify({
        "emotion": emotion_data["emotion"],
        "intensity": emotion_data["intensity"],
        "scores": emotion_data["scores"],
        "voice_params": voice_params,
    })


@app.route("/synthesize", methods=["POST"])
def synthesize():
    """Full pipeline: detect emotion → map to voice params → generate audio."""
    data = request.get_json(force=True)
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400

    # 1. Detect emotion
    emotion_data = detect_emotion(text)

    # 2. Map to voice parameters
    voice_params = get_voice_params(emotion_data["emotion"], emotion_data["intensity"])

    # 3. Generate SSML
    ssml = generate_ssml(text, emotion_data["emotion"], emotion_data["intensity"], voice_params)

    # 4. Synthesize audio
    filename = f"{uuid.uuid4().hex}.wav"
    output_path = os.path.join(AUDIO_DIR, filename)
    synthesize_speech(text, voice_params, output_path)

    audio_url = f"/static/audio/{filename}"

    return jsonify({
        "emotion": emotion_data["emotion"],
        "intensity": emotion_data["intensity"],
        "scores": emotion_data["scores"],
        "voice_params": voice_params,
        "ssml": ssml,
        "audio_url": audio_url,
        "audio_filename": filename,
    })


if __name__ == "__main__":
    print("🎙️  Empathy Engine starting on http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
