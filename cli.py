#!/usr/bin/env python3
"""
Empathy Engine - CLI Interface
Usage: python cli.py "Your text here"
       python cli.py  (interactive mode)
"""

import sys
import os
import argparse

# Add parent dir to path so we can import from app.py
sys.path.insert(0, os.path.dirname(__file__))

from app import detect_emotion, get_voice_params, synthesize_speech, generate_ssml

EMOTION_ICONS = {
    "joy": "😄", "sadness": "😢", "anger": "😠",
    "fear": "😰", "surprise": "😲", "inquisitive": "🤔", "neutral": "😐",
}


def print_banner():
    print("\n" + "═" * 60)
    print("  🎙️  EMPATHY ENGINE  — Emotionally Intelligent TTS")
    print("═" * 60 + "\n")


def run_pipeline(text: str, output_path: str = None, verbose: bool = True):
    """Full pipeline: detect → map → synthesize."""

    if verbose:
        print(f"  📝  Input: \"{text[:80]}{'...' if len(text) > 80 else ''}\"")
        print()

    # 1. Emotion Detection
    emotion_data = detect_emotion(text)
    emotion = emotion_data["emotion"]
    intensity = emotion_data["intensity"]
    icon = EMOTION_ICONS.get(emotion, "🙂")

    if verbose:
        print(f"  {icon}  Detected Emotion   : {emotion.upper()}")
        print(f"  📊  Intensity          : {intensity*100:.0f}%")
        print()
        print("  Emotion Scores:")
        max_score = max(emotion_data["scores"].values()) or 1
        for em, score in sorted(emotion_data["scores"].items(), key=lambda x: -x[1]):
            bar_len = int((score / max_score) * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"    {em:<12} {bar} {score:.2f}")
        print()

    # 2. Voice Parameter Mapping
    voice_params = get_voice_params(emotion, intensity)

    if verbose:
        print(f"  🎛️   Voice Style         : {voice_params['description']}")
        print(f"  ⏱️   Rate               : {voice_params['rate']:.2f}× normal")
        print(f"  🎵  Pitch              : {voice_params['pitch_st']:+.1f} semitones")
        print(f"  🔊  Volume             : {voice_params['volume']:.2f}× normal")
        print()

    # 3. SSML
    ssml = generate_ssml(text, emotion, intensity, voice_params)
    if verbose:
        print("  SSML Markup:")
        for line in ssml.split('\n'):
            print("   ", line)
        print()

    # 4. Audio synthesis
    if output_path is None:
        output_path = f"output_{emotion}.wav"

    if verbose:
        print(f"  🔄  Synthesizing audio...")

    success = synthesize_speech(text, voice_params, output_path)

    if verbose:
        if success and os.path.exists(output_path):
            size = os.path.getsize(output_path)
            print(f"  ✅  Audio saved        : {output_path} ({size:,} bytes)")
        else:
            print(f"  ❌  Synthesis failed")
        print()

    return {
        "emotion": emotion,
        "intensity": intensity,
        "voice_params": voice_params,
        "output_path": output_path,
        "success": success,
    }


def interactive_mode():
    print_banner()
    print("  Interactive Mode — type 'quit' to exit\n")

    while True:
        try:
            text = input("  Enter text: ").strip()
            if text.lower() in ("quit", "exit", "q"):
                print("\n  Goodbye!\n")
                break
            if not text:
                continue

            output = input("  Output file [output.wav]: ").strip() or "output.wav"
            print()
            run_pipeline(text, output)
            print("─" * 60 + "\n")

        except KeyboardInterrupt:
            print("\n\n  Interrupted. Goodbye!\n")
            break


def main():
    parser = argparse.ArgumentParser(
        description="Empathy Engine — Emotionally Intelligent Text-to-Speech"
    )
    parser.add_argument("text", nargs="?", help="Text to synthesize")
    parser.add_argument("-o", "--output", default=None, help="Output WAV file path")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress verbose output")
    parser.add_argument("--analyze-only", action="store_true", help="Only run emotion analysis, no audio")
    args = parser.parse_args()

    if args.text:
        print_banner()
        if args.analyze_only:
            ed = detect_emotion(args.text)
            vp = get_voice_params(ed["emotion"], ed["intensity"])
            print(f"Emotion: {ed['emotion']} | Intensity: {ed['intensity']*100:.0f}%")
            print(f"Scores: {ed['scores']}")
            print(f"Voice: rate={vp['rate']:.2f}, pitch={vp['pitch_st']:+.1f}st, vol={vp['volume']:.2f}")
        else:
            run_pipeline(args.text, args.output, verbose=not args.quiet)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
