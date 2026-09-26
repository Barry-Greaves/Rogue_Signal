"""Upscale an approved clip with SeedVR2, keeping its performance exactly.

A new H3 render at a higher resolution is a new performance (same seed,
different words). SeedVR2 restores and enlarges the approved draft instead,
so the words, lip sync and timing Barry signed off stay the same.

    python upscale.py runs/ep002/ep002-b --size 1080 1080
    python upscale.py runs/ep002/ep002-b --size 1080 1080 --name ep002-b-up --color lab

Writes runs/<group>/<name>/clip.mp4, audio.wav and render-manifest.json
(the source clip's spec is copied in, so captions.py and verify_speech.py
work on the result unchanged). Standard library only; uses presenter.py's
ComfyUI helpers. Graph follows ComfyUI's utility_seedvr2_3b_int8_upscale_video
template, with temporal chunking on so a 15 s clip fits in 16 GB of VRAM.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.parse

import presenter

ROOT = presenter.ROOT
MODELS = {"unet": "seedvr2_3b_int8_convrot.safetensors", "vae": "seedvr2_ema_vae_fp16.safetensors"}


def build_graph(video_name, multiplier, seed, color, name):
    tiled = {"tile_size": 512, "overlap": 128, "temporal_size": 64, "temporal_overlap": 8}
    return {
        "load": {"class_type": "LoadVideo", "inputs": {"file": video_name}},
        "parts": {"class_type": "GetVideoComponents", "inputs": {"video": ["load", 0]}},
        # "scale by multiplier" is the template's mode; "scale dimensions" was
        # accepted but silently left the frames at their source size.
        "resize": {"class_type": "ResizeImageMaskNode", "inputs": {
            "input": ["parts", 0], "resize_type": "scale by multiplier",
            "resize_type.multiplier": multiplier, "scale_method": "lanczos"}},
        "pre": {"class_type": "SeedVR2Preprocess", "inputs": {"resized_images": ["resize", 0]}},
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": MODELS["unet"], "weight_dtype": "default"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": MODELS["vae"]}},
        "encode": {"class_type": "VAEEncodeTiled", "inputs": {"pixels": ["pre", 0], "vae": ["vae", 0], **tiled}},
        "chunk": {"class_type": "SeedVR2TemporalChunk", "inputs": {
            "latent": ["encode", 0], "temporal_overlap": 0, "chunking_mode": "auto"}},
        "cond": {"class_type": "SeedVR2Conditioning", "inputs": {"model": ["unet", 0], "vae_conditioning": ["chunk", 0]}},
        "sample": {"class_type": "KSampler", "inputs": {
            "model": ["unet", 0], "seed": seed, "steps": 1, "cfg": 1.0, "sampler_name": "euler",
            "scheduler": "simple", "positive": ["cond", 0], "negative": ["cond", 1],
            "latent_image": ["chunk", 0], "denoise": 1.0}},
        "merge": {"class_type": "SeedVR2TemporalMerge", "inputs": {"latents": ["sample", 0], "temporal_overlap": ["chunk", 1]}},
        "decode": {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["merge", 0], "vae": ["vae", 0], **tiled}},
        "post": {"class_type": "SeedVR2PostProcessing", "inputs": {
            "images": ["decode", 0], "original_resized_images": ["resize", 0], "color_correction_method": color}},
        "video": {"class_type": "CreateVideo", "inputs": {"images": ["post", 0], "audio": ["parts", 1], "fps": ["parts", 2]}},
        "save": {"class_type": "SaveVideo", "inputs": {
            "video": ["video", 0], "filename_prefix": f"rogue_signal/{name}", "format": "auto", "codec": "auto"}},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", help="run folder of the approved clip (contains clip.mp4 and render-manifest.json)")
    parser.add_argument("--size", nargs=2, type=int, metavar=("W", "H"), default=[1080, 1080])
    parser.add_argument("--name", help="output run name (default: <source>-up)")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--color", default="lab", choices=["lab", "wavelet", "adain", "none"],
                        help="colour matching to the source (template default is none)")
    parser.add_argument("--timeout", type=int, default=3600)
    args = parser.parse_args()

    src = ROOT / args.source
    manifest = json.loads((src / "render-manifest.json").read_text(encoding="utf-8"))
    name = args.name or src.name + "-up"
    out = src.parent / name
    out.mkdir(parents=True, exist_ok=True)

    video_name = presenter.upload(src / "clip.mp4")
    src_w = manifest["spec"]["width"]
    multiplier = round(args.size[0] / src_w, 4)
    if round(src_w * multiplier) != args.size[0] or round(manifest["spec"]["height"] * multiplier) != args.size[1]:
        raise SystemExit(f"--size {args.size} is not a uniform scale of the {src_w}x{manifest["spec"]["height"]} source")
    graph = build_graph(video_name, multiplier, args.seed, args.color, name)
    (out / "api-graph.json").write_text(json.dumps(graph, indent=2), encoding="utf-8")
    started = time.time()
    prompt_id = presenter.api("/prompt", {"prompt": graph, "client_id": "rogue-signal"})["prompt_id"]
    print(f"queued {name}: {prompt_id} ({args.size[0]}x{args.size[1]}, x{multiplier} from {src.name})", flush=True)
    entry = presenter.wait(prompt_id, args.timeout)
    elapsed = round(time.time() - started, 1)
    # Take the SaveVideo node's file only: LoadVideo also lists the uploaded
    # source in the outputs, and picking that one silently "upscales" nothing.
    files = [f for v in entry["outputs"].get("save", {}).values() if isinstance(v, list)
             for f in v if isinstance(f, dict) and "filename" in f and f.get("type") == "output"]
    if not files:
        raise SystemExit("Job finished without an output file.")
    f = files[0]
    query = urllib.parse.urlencode({"filename": f["filename"], "subfolder": f.get("subfolder", ""), "type": f.get("type", "output")})
    clip = out / "clip.mp4"
    clip.write_bytes(presenter.api(f"/view?{query}"))
    result = {
        # Keep the source spec so captions.py / verify_speech.py see the approved line.
        "spec": {**manifest["spec"], "name": name, "width": args.size[0], "height": args.size[1]},
        "upscaled_from": {"run": str(src.relative_to(ROOT)), "output_sha256": manifest.get("output_sha256"),
                          "prompt_id": manifest.get("prompt_id")},
        "upscaler": {"models": MODELS, "seed": args.seed, "color_correction": args.color},
        "frames": manifest.get("frames"), "fps": manifest.get("fps"), "seconds": manifest.get("seconds"),
        "prompt_id": prompt_id, "elapsed_seconds": elapsed, "comfy_output": f,
        "output": str(clip.relative_to(ROOT)), "output_sha256": presenter.sha256(clip),
        "rendered_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (out / "render-manifest.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    if shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-vn", "-ac", "2", "-ar", "48000",
                        str(out / "audio.wav")], check=False)
    print(f"done {name} in {elapsed}s -> {clip}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
