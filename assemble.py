"""Join rendered clips into one 1080x1920 episode, full-frame or split-screen.

Standard library plus FFmpeg. Every clip is trimmed to --clip-seconds (H3
renders 362 frames, 15.083 s), so N clips make exactly N x 15 s.

Full frame (Episodes 000-001):

    python assemble.py full --clips runs/ep002/a runs/ep002/b runs/ep002/c \
        --out runs/ep002/ep002-1080x1920.mp4

Split screen: presenter on top, article screenshots below. Panels switch on
their own schedule, independent of the clip cuts ("file@start_seconds";
without @ they are spread evenly over the episode):

    python assemble.py split --clips runs/ep002/a runs/ep002/b runs/ep002/c \
        --panels p1.png p2.png p3.png p4.png p5.png p6.png \
        --out runs/ep002/ep002-split.mp4

Add subtitles afterwards with captions.py (--margin-v 870 puts them at the
bottom of a 1080 px presenter panel). Clip arguments are run folders
containing clip.mp4, or .mp4 files.
"""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
W, H, FPS = 1080, 1920, 24
SHARPEN = "unsharp=5:5:0.35:5:5:0"


def clip_path(arg):
    p = ROOT / arg
    return p / "clip.mp4" if p.is_dir() else p


def panel_schedule(specs, total):
    """[(path, start, end)] from 'file' or 'file@seconds' arguments."""
    parsed = []
    for i, spec in enumerate(specs):
        path, _, at = spec.rpartition("@") if "@" in spec else (spec, "", "")
        start = float(at) if at else total * i / len(specs)
        parsed.append((path, start))
    if parsed[0][1] != 0:
        raise ValueError("The first panel must start at 0 s")
    starts = [s for _, s in parsed]
    if starts != sorted(starts) or len(set(starts)) != len(starts):
        raise ValueError("Panel start times must increase")
    ends = starts[1:] + [total]
    if ends[-1] <= starts[-1]:
        raise ValueError("The last panel starts after the episode ends")
    return [(p, s, e) for (p, s), e in zip(parsed, ends)]


def presenter_chain(n, clip_seconds, width, height, crop_y):
    """Trim each clip, crop to the panel's aspect, scale to width x height."""
    parts = []
    for i in range(n):
        # Crop the largest region with the panel's aspect ratio, anchored at
        # crop_y from the top (the face sits in the upper part of a portrait
        # render). A square render into a square panel passes through whole.
        crop = (f"crop='min(iw,ih*{width}/{height})':'min(ih,iw*{height}/{width})':"
                f"'(iw-min(iw,ih*{width}/{height}))/2':'min({crop_y},ih-min(ih,iw*{height}/{width}))'")
        parts.append(f"[{i}:v]trim=end={clip_seconds},setpts=PTS-STARTPTS,{crop},"
                     f"scale={width}:{height}:flags=lanczos,{SHARPEN},setsar=1,fps={FPS}[v{i}]")
        parts.append(f"[{i}:a]atrim=end={clip_seconds},asetpts=PTS-STARTPTS,aresample=48000[a{i}]")
    joined = "".join(f"[v{i}][a{i}]" for i in range(n))
    parts.append(f"{joined}concat=n={n}:v=1:a=1[pres][aout]")
    return parts


def panel_chain(schedule, first_input, height, scale, pad_x, pad_top, bg):
    """Article screenshots, scaled and placed top-left on a background."""
    parts, inner = [], int(W * scale)
    for k, (_, start, end) in enumerate(schedule):
        i = first_input + k
        parts.append(f"[{i}:v]trim=duration={end - start:.3f},setpts=PTS-STARTPTS,"
                     f"scale={inner}:-2:flags=lanczos,crop={inner}:'min(ih,{height - pad_top})':0:0,"
                     f"pad={W}:{height}:{pad_x}:{pad_top}:color={bg},setsar=1,fps={FPS},format=yuv420p[p{k}]")
    joined = "".join(f"[p{k}]" for k in range(len(schedule)))
    parts.append(f"{joined}concat=n={len(schedule)}:v=1:a=0[art]")
    return parts


def build(args):
    clips = [clip_path(c) for c in args.clips]
    missing = [str(c) for c in clips if not c.exists()]
    if missing:
        raise SystemExit(f"Missing clips: {', '.join(missing)}")
    total = len(clips) * args.clip_seconds
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for c in clips:
        cmd += ["-i", str(c)]
    if args.layout == "full":
        graph = presenter_chain(len(clips), args.clip_seconds, W, H, args.crop_y)
        graph.append("[pres]format=yuv420p[vout]")
    else:
        schedule = panel_schedule(args.panels, total)
        for path, start, end in schedule:
            cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{end - start:.3f}", "-i", str(ROOT / path)]
        panel_h = H - args.top_height
        graph = presenter_chain(len(clips), args.clip_seconds, W, args.top_height, args.crop_y)
        graph += panel_chain(schedule, len(clips), panel_h, args.panel_scale, args.panel_x, args.panel_top, args.bg)
        graph.append("[pres]format=yuv420p[top];[top][art]vstack,format=yuv420p[vout]")
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd += ["-filter_complex", ";".join(graph), "-map", "[vout]", "-map", "[aout]",
            "-t", f"{total:.3f}", "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    return cmd, out, total


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("layout", choices=["full", "split"])
    parser.add_argument("--clips", nargs="+", required=True, help="clip folders or .mp4 files, in order")
    parser.add_argument("--out", required=True)
    parser.add_argument("--clip-seconds", type=float, default=15.0)
    parser.add_argument("--crop-y", type=int, default=0, help="crop offset from the top of each clip, px")
    split = parser.add_argument_group("split layout")
    split.add_argument("--panels", nargs="+", help="article images, 'file' or 'file@start_seconds'")
    split.add_argument("--top-height", type=int, default=1080, help="presenter panel height, px")
    split.add_argument("--panel-scale", type=float, default=0.85,
                       help="article width as a share of 1080 px; <1 keeps text clear of YouTube's right-hand buttons")
    split.add_argument("--panel-x", type=int, default=0, help="article left offset, px")
    split.add_argument("--panel-top", type=int, default=40, help="space above the article, px")
    split.add_argument("--bg", default="0x101517", help="article panel background (the website's)")
    parser.add_argument("--dry-run", action="store_true", help="print the FFmpeg command without running it")
    args = parser.parse_args()
    if args.layout == "split" and not args.panels:
        parser.error("split layout needs --panels")
    cmd, out, total = build(args)
    if args.dry_run:
        print(subprocess.list2cmdline(cmd))
        return 0
    subprocess.run(cmd, check=True)
    print(f"wrote {out} ({total:.3f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
