"""Finish an upscaled clip: soften SeedVR2's skin, add film grain and a room sound.

SeedVR2 over-sharpens skin (freckles and pores look etched). Blending its
output with a plain Lanczos upscale of the same approved draft keeps the eyes
crisp and lets skin read as skin. The frames are the same, so the words, lip
sync and timing Barry approved do not change. Chosen by Barry on 2026-09-28
(60/40 blend; see the vault note "2026-09-28 Finishing and Upscale Blend Test").

    python finish.py runs/ep004/ep004-a-up
    python finish.py runs/ep004/ep004-a-up --blend 0.7 --name ep004-a-test

Writes runs/<group>/<name>/ (default <upscaled name> with -up -> -fin):
clip.mp4, audio.wav and render-manifest.json, with the spec copied so
verify_speech.py and captions.py work on it unchanged. Needs FFmpeg.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

# Lifted blacks, softened highlights, 6% less saturation, light vignette,
# fine grain that changes every frame.
GRADE = ("curves=all='0/0.025 0.5/0.5 1/0.965',eq=saturation=0.94,vignette=angle=0.38,"
         "noise=c0s=7:c0f=t+u:c1s=3:c1f=t+u:c2s=3:c2f=t+u,format=yuv420p")
# Low cut, a little warmth, softer sibilance, three short room reflections;
# the volume trim keeps the level within 0.1 dB of the source.
ROOM = ("highpass=f=85,equalizer=f=220:t=q:w=1.2:g=1.5,equalizer=f=6500:t=q:w=1.5:g=-1.5,"
        "aecho=1.0:0.9:11|17|26:0.10|0.07|0.045,volume=-0.3dB,alimiter=limit=0.94")


def filter_graph(blend, size):
    w, h = size
    return (f"[0:v]format=gbrp[s];[1:v]scale={w}:{h}:flags=lanczos,format=gbrp[l];"
            f"[s][l]blend=all_expr='A*{blend}+B*{1 - blend:.2f}',{GRADE}[v];[0:a]{ROOM}[a]")


def probe_size(clip):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height", "-of", "csv=p=0", str(clip)],
                         capture_output=True, text=True, check=True).stdout
    w, h = out.strip().split(",")[:2]
    return int(w), int(h)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run", help="upscaled clip folder (from upscale.py)")
    p.add_argument("--blend", type=float, default=0.6, help="share of the SeedVR2 image (default 0.6)")
    p.add_argument("--name", help="output folder name (default: -up -> -fin)")
    a = p.parse_args()

    src = (ROOT / a.run).resolve()
    manifest = json.loads((src / "render-manifest.json").read_text(encoding="utf-8"))
    draft = ROOT / manifest["upscaled_from"]["run"] / "clip.mp4"
    if not draft.exists():
        sys.exit(f"source draft not found: {draft}")
    name = a.name or (src.name[:-3] + "-fin" if src.name.endswith("-up") else src.name + "-fin")
    out = src.parent / name
    out.mkdir(exist_ok=True)

    clip = out / "clip.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src / "clip.mp4"), "-i", str(draft),
                    "-filter_complex", filter_graph(a.blend, probe_size(src / "clip.mp4")),
                    "-map", "[v]", "-map", "[a]", "-shortest", "-c:v", "libx264", "-crf", "16",
                    "-preset", "slow", "-c:a", "aac", "-b:a", "192k", str(clip)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-vn", "-ar", "48000",
                    str(out / "audio.wav")], check=True)

    manifest["finished_from"] = {"run": str(src.relative_to(ROOT)), "draft": str(draft.relative_to(ROOT)),
                                 "blend": a.blend, "grade": GRADE, "room": ROOM}
    manifest["output"] = str(clip.relative_to(ROOT))
    (out / "render-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"done {name} (blend {a.blend:.2f}) -> {clip}")


if __name__ == "__main__":
    main()
