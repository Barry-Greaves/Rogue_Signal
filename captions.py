"""Build subtle subtitles for an episode and burn them into the video.

Standard library plus FFmpeg (libass). The caption text is the approved
script from each clip's render manifest, never Whisper's transcript, so
names keep their approved spelling ("ART", "CRISPR"). Timing comes from the
word timestamps verify_speech.py saved in speech-check.json; words Whisper
missed are placed between their neighbours.

    python captions.py --clips runs/ep001/ep001-a-768-s1 runs/ep001/ep001-b-768 \
        --video runs/ep001/ep001-1080x1920.mp4 --out runs/ep001/ep001-captioned.mp4

Clip N is assumed to start at N * --clip-seconds in the joined video.
"""
import argparse
import difflib
import json
from pathlib import Path
import subprocess
import sys

from verify_speech import words

ROOT = Path(__file__).resolve().parent
FONT_DIR = ROOT / "assets" / "fonts"
MAX_CHARS = 26  # per caption; short lines stay subtle and readable on a phone

# "DM Sans 9pt" is the font's own family name (ID 1); plain "DM Sans"
# silently falls back to Arial. PlayRes matches the 1080x1920 delivery. MarginV keeps captions above the
# Shorts title/description overlay at the bottom of the screen.
ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,DM Sans 9pt,64,&H00FFFFFF,&H00FFFFFF,&H99000000,&H66000000,0,0,0,0,100,100,0,0,1,2.2,1.5,2,90,90,500,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def token_times(line, heard):
    """(token, start, end) for each whitespace token of the approved line."""
    tokens = line.split()
    expected, owner = [], []
    for i, token in enumerate(tokens):
        for w in words(token):
            expected.append(w)
            owner.append(i)
    got, spans = [], []
    for h in heard:
        for w in words(h["word"]):
            got.append(w)
            spans.append((h["start"], h["end"]))
    times = [None] * len(expected)
    matcher = difflib.SequenceMatcher(a=expected, b=got, autojunk=False)
    for block in matcher.get_matching_blocks():
        for k in range(block.size):
            times[block.a + k] = spans[block.b + k]
    known = [i for i, t in enumerate(times) if t]
    if not known:
        raise SystemExit("No transcribed words line up with the script; check speech-check.json.")
    for i, t in enumerate(times):  # interpolate words Whisper missed
        if t is None:
            before = max((k for k in known if k < i), default=None)
            after = min((k for k in known if k > i), default=None)
            start = times[before][1] if before is not None else times[after][0]
            end = times[after][0] if after is not None else start + 0.3
            times[i] = (start, max(start, end))
    out = []
    for i, token in enumerate(tokens):
        subs = [times[k] for k, o in enumerate(owner) if o == i]
        if subs:
            out.append((token, subs[0][0], subs[-1][1]))
        elif out:  # token with no letters, e.g. a dash: attach to previous
            out[-1] = (out[-1][0] + " " + token, out[-1][1], out[-1][2])
    return out


LEADING = {"a", "an", "the", "its", "and", "but", "or", "of", "to", "in", "yet"}


def chunks(timed):
    """Group words into short captions, breaking at punctuation when possible.

    A line never ends on a small word that belongs with what follows
    ("a DNA repeat array and an / accessory protein" becomes
    "a DNA repeat array / and an accessory protein").
    """
    groups, current = [], []
    for token, start, end in timed:
        text = " ".join(t for t, _, _ in current + [(token, 0, 0)])
        # A few extra characters are allowed to finish a sentence rather
        # than strand its last word ("features:") on a line of its own.
        limit = MAX_CHARS + (8 if token[-1] in ".:;!?" else 0)
        if current and len(text) > limit:
            carry = []
            while len(current) > 1 and current[-1][0].lower().strip(",.:;") in LEADING:
                carry.insert(0, current.pop())
            groups.append(current)
            current = carry
        current.append((token, start, end))
        if token[-1] in ".:;!?" or (token[-1] == "," and len(current) >= 2):
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def stamp(seconds):
    cs = int(round(seconds * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def build_ass(clip_dirs, clip_seconds):
    events = []
    for n, folder in enumerate(clip_dirs):
        folder = ROOT / folder
        line = json.loads((folder / "render-manifest.json").read_text(encoding="utf-8"))["spec"]["line"]
        heard = json.loads((folder / "speech-check.json").read_text(encoding="utf-8"))["words"]
        groups = chunks(token_times(line, heard))
        offset, clip_end = n * clip_seconds, (n + 1) * clip_seconds
        for i, group in enumerate(groups):
            start = offset + group[0][1]
            nxt = offset + groups[i + 1][0][1] if i + 1 < len(groups) else offset + group[-1][2] + 0.4
            end = min(nxt, clip_end - 0.05)
            text = " ".join(t for t, _, _ in group)
            events.append((start, end, text))
    body = "".join(f"Dialogue: 0,{stamp(s)},{stamp(e)},Sub,,0,0,0,,{t}\n" for s, e, t in events)
    return ASS_HEADER + body, events


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clips", nargs="+", required=True, help="clip run folders, in episode order")
    parser.add_argument("--video", help="joined 1080x1920 episode to burn captions into")
    parser.add_argument("--out", help="output video (default: <video>-captioned.mp4)")
    parser.add_argument("--clip-seconds", type=float, default=15.0)
    args = parser.parse_args()

    ass, events = build_ass(args.clips, args.clip_seconds)
    first = (ROOT / args.clips[0]).parent
    ass_path = first / "captions.ass"
    ass_path.write_text(ass, encoding="utf-8")
    for s, e, t in events:
        print(f"{s:6.2f}-{e:6.2f}  {t}")
    print(f"wrote {ass_path}")
    if not args.video:
        return 0
    video = ROOT / args.video
    out = ROOT / args.out if args.out else video.with_name(video.stem + "-captioned.mp4")
    # libass paths are awkward on Windows (drive colons), so run FFmpeg from the
    # captions folder with relative paths.
    fonts = Path(__import__("os").path.relpath(FONT_DIR, ass_path.parent)).as_posix()
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(video),
           "-vf", f"subtitles=captions.ass:fontsdir={fonts}",
           "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-c:a", "copy", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, cwd=ass_path.parent, check=True)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
