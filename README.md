# 🎙️ Empathy Engine

> *Emotionally Intelligent Text-to-Speech — bridging the gap between text and human voice.*

The Empathy Engine analyzes the emotional content of any text and dynamically modulates synthesized speech to match — speaking with joy, sadness, anger, curiosity, or calm, just like a human would.

---

## ✨ Features

| Feature | Details |
|---|---|
| **6 + 1 Emotions** | Joy, Sadness, Anger, Fear, Surprise, Inquisitive, Neutral |
| **Intensity Scaling** | Soft "this is good" vs explosive "BEST NEWS EVER!!" |
| **3 Voice Parameters** | Rate (speed), Pitch (semitones), Volume |
| **SSML Output** | Full Speech Synthesis Markup Language generation |
| **Web UI** | Clean, live-updating browser interface with embedded player |
| **CLI** | Interactive or single-shot terminal usage |

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/nabilrizz/Empathy-Engine
cd Darwix

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. (Recommended) Install espeak for best audio quality

```bash
# Ubuntu / Debian
sudo apt-get install espeak ffmpeg

# macOS
brew install espeak ffmpeg

# Windows — download espeak installer from http://espeak.sourceforge.net/
```

> **Note:** If espeak is unavailable, the engine falls back to gTTS (requires internet) or pyttsx3 automatically.

### 3. Run the Web Interface

```bash
python app.py
```

Open **http://localhost:5000** in your browser. Type any text and click **Synthesize Speech**.

### 4. Run via CLI

```bash
# Single shot
python cli.py "I just got promoted! This is the best day of my life!"

# Specify output file
python cli.py "I'm so worried about tomorrow" -o worried.wav

# Analyze emotions only, no audio
python cli.py "This is amazing news!" --analyze-only

# Interactive mode
python cli.py
```

---

## 🧠 How It Works

### Emotion Detection

The engine uses a **lexicon-based approach with contextual modifiers**:

1. **Word Scoring** — Each word is checked against a curated emotion lexicon of ~70 entries. Every match contributes a weighted score to one of 7 emotional categories.

2. **Intensifier Boost** — Words preceded by intensifiers (`very`, `extremely`, `absolutely`, etc.) receive a 1.5× weight multiplier.

3. **Negation Handling** — Words within 3 tokens of a negator (`not`, `never`, `no`, etc.) have their emotion flipped (e.g. "not happy" → contributes to sadness).

4. **Structural Signals** — Exclamation marks boost joy/surprise scores; question marks boost inquisitive; high caps ratio boosts anger.

5. **Intensity Score** — The dominant emotion's raw score is normalized to a 0–1 intensity value, clamped at a "max raw signal" of 3.0.

### Emotion → Voice Mapping

Each emotion has a **base voice profile** (rate, pitch in semitones, volume). The actual parameters are **linearly interpolated** between the neutral baseline and the emotion's base profile, scaled by intensity:

```
param = neutral_param + (emotion_param - neutral_param) × intensity
```

| Emotion | Rate | Pitch | Volume | Style |
|---|---|---|---|---|
| **Joy** | ×1.20 | +3.0 st | ×1.10 | Upbeat, enthusiastic |
| **Sadness** | ×0.80 | −2.5 st | ×0.85 | Soft, subdued |
| **Anger** | ×1.30 | +1.5 st | ×1.25 | Firm, forceful |
| **Fear** | ×1.15 | +1.0 st | ×0.90 | Tense, cautious |
| **Surprise** | ×1.25 | +4.0 st | ×1.15 | High, animated |
| **Inquisitive** | ×0.95 | +1.5 st | ×0.95 | Measured, curious |
| **Neutral** | ×1.00 | 0.0 st | ×1.00 | Calm, balanced |

This means "This is good" (low intensity joy) gets a subtle pitch bump, while "THIS IS THE BEST NEWS EVER!!!" (high intensity joy) gets the full rate acceleration and pitch lift.

### Audio Synthesis Pipeline

The engine tries three TTS backends in order:

1. **espeak** (local, fastest, offline) — parameters are mapped directly to espeak's `words-per-minute`, `pitch` (0–99), and `amplitude` flags
2. **gTTS** (Google TTS, requires internet) — rate parameter selects slow/normal mode; pitch and volume applied via ffmpeg post-processing
3. **pyttsx3** (local, OS voices) — cross-platform fallback
4. **Tone WAV** (pure Python) — deterministic sine-wave audio always produced as a last resort

### SSML Generation

The engine produces [SSML](https://www.w3.org/TR/speech-synthesis/) markup using the `<prosody>` tag with rate, pitch, and volume attributes. This markup can be used directly with cloud TTS APIs (Google Cloud TTS, AWS Polly, Azure Cognitive Services) for production-quality output.

---

## 📁 Project Structure

```
empathy-engine/
├── app.py              # Flask server + emotion engine + synthesis pipeline
├── cli.py              # Command-line interface
├── requirements.txt    # Python dependencies
├── README.md
├── templates/
│   └── index.html      # Web UI
└── static/
    └── audio/          # Generated audio files (auto-created)
```

---

## 🔧 API Endpoints

### `POST /analyze`
Analyze emotion without generating audio.

```json
// Request
{ "text": "I'm so excited about this!" }

// Response
{
  "emotion": "joy",
  "intensity": 0.73,
  "scores": { "joy": 2.2, "sadness": 0, ... },
  "voice_params": { "rate": 1.15, "pitch_st": 2.19, "volume": 1.07, "description": "Upbeat and enthusiastic" }
}
```

### `POST /synthesize`
Full pipeline — emotion detection + audio generation.

```json
// Request
{ "text": "This is terrible news." }

// Response
{
  "emotion": "sadness",
  "intensity": 0.67,
  "scores": { ... },
  "voice_params": { "rate": 0.87, "pitch_st": -1.67, "volume": 0.90, "description": "Soft and subdued" },
  "ssml": "<speak>...</speak>",
  "audio_url": "/static/audio/abc123.wav",
  "audio_filename": "abc123.wav"
}
```

---

## 🎯 Design Decisions

- **No ML dependency** — The emotion lexicon approach means zero model download time and instant startup. For production, drop in a Hugging Face model at the detection layer without changing anything else.
- **Intensity scaling** — A linear interpolation gives smooth, predictable parameter modulation. Non-linear curves could be added per-emotion for more dramatic effect.
- **Fallback chain** — The synthesis pipeline always produces output, making demos reliable regardless of the host environment.
- **SSML output** — Even when using local TTS, SSML is generated so the project is ready to plug into cloud TTS APIs for production-quality voices.

---
