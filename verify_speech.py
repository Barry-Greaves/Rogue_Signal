"""Check that a rendered clip speaks the approved line, word for word.

Needs faster-whisper, kept out of the stdlib-only core scripts:

    python verify_speech.py runs/tests/test-a1
    python verify_speech.py runs/tests/test-a1 --model small.en

Reads the clip's render-manifest.json for the expected line, transcribes
audio.wav (or clip.mp4) on the CPU so it never competes with ComfyUI for
VRAM, and writes speech-check.json next to the clip. Exits 1 on a mismatch.
"""
import argparse
import array
import difflib
import json
import math
from pathlib import Path
import re
import sys
import wave

ROOT = Path(__file__).resolve().parent


ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def spell(token):
    """Whisper writes '30' where the script says 'thirty'; compare them as words."""
    if not token.isdigit() or int(token) > 99:
        return [token]
    n = int(token)
    return [ONES[n]] if n < 20 else [TENS[n // 10]] + ([ONES[n % 10]] if n % 10 else [])


def words(text):
    tokens = re.findall(r"[a-z0-9']+", text.lower().replace("’", "'").replace("-", " "))
    return [w for t in tokens for w in spell(t)]


def compare(expected, heard):
    """Word-level diff: which words were missing, added or changed."""
    edits = []
    matcher = difflib.SequenceMatcher(a=expected, b=heard, autojunk=False)
    for op, a1, a2, b1, b2 in matcher.get_opcodes():
        if op != "equal":
            edits.append({"op": op, "expected": " ".join(expected[a1:a2]), "heard": " ".join(heard[b1:b2])})
    errors = sum(max(e["expected"].count(" ") + bool(e["expected"]), e["heard"].count(" ") + bool(e["heard"]))
                 for e in edits)
    return edits, errors / max(len(expected), 1)


def loud_after(wav_path, after, threshold_db=-30.0, window=0.3):
    """Seconds where speech-level audio continues after the transcript ends.

    Whisper can silently drop a repeated phrase, so the transcript alone is
    not proof that nothing else was said.
    """
    with wave.open(str(wav_path), "rb") as w:
        rate, channels = w.getframerate(), w.getnchannels()
        samples = array.array("h", w.readframes(w.getnframes()))
    step = int(rate * window) * channels
    loud = []
    for i in range(int((after + 0.3) * rate) * channels, len(samples) - step + 1, step):
        chunk = samples[i:i + step]
        rms = math.sqrt(sum(s * s for s in chunk) / len(chunk)) or 1e-9
        if 20 * math.log10(rms / 32768) > threshold_db:
            loud.append(round(i / channels / rate, 2))
    return loud


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir")
    parser.add_argument("--model", default="small.en")
    parser.add_argument("--line", help="expected words; defaults to the manifest's spec.line")
    args = parser.parse_args()

    folder = (ROOT / args.run_dir).resolve()
    manifest = json.loads((folder / "render-manifest.json").read_text(encoding="utf-8"))
    expected_text = args.line or manifest["spec"]["line"]
    audio = folder / "audio.wav"
    if not audio.exists():
        raise SystemExit(f"{audio} missing; presenter.py extracts it with ffmpeg after each render.")

    from faster_whisper import WhisperModel
    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    # VAD transcribes each burst of speech separately; without it Whisper
    # tends to swallow a repeated phrase into the previous one.
    segments, _ = model.transcribe(str(audio), language="en", beam_size=5, word_timestamps=True,
                                   condition_on_previous_text=False, vad_filter=True,
                                   vad_parameters={"min_silence_duration_ms": 250})
    timed = [{"word": w.word.strip(), "start": round(w.start, 2), "end": round(w.end, 2)}
             for s in segments for w in (s.words or [])]
    heard_text = " ".join(w["word"] for w in timed)
    edits, error_rate = compare(words(expected_text), words(heard_text))
    speech_end = timed[-1]["end"] if timed else 0.0
    untranscribed = loud_after(audio, speech_end)
    result = {
        "passed": not edits and not untranscribed, "word_error_rate": round(error_rate, 3),
        "expected": expected_text, "heard": heard_text, "edits": edits,
        "untranscribed_audio_at": untranscribed,
        "speech_start": timed[0]["start"] if timed else None, "speech_end": speech_end,
        "clip_seconds": manifest.get("seconds"), "model": args.model, "words": timed,
    }
    (folder / "speech-check.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{'PASS' if result['passed'] else 'FAIL'} {folder.name}  WER {result['word_error_rate']:.0%}  "
          f"speech {result['speech_start']}-{result['speech_end']}s of {result['clip_seconds']}s")
    print(f"  heard: {heard_text}")
    for e in edits:
        print(f"  {e['op']}: expected '{e['expected']}' heard '{e['heard']}'")
    if untranscribed:
        print(f"  speech-level audio after the last word at {untranscribed[0]}s: listen for an extra phrase")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
