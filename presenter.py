"""Render one presenter clip with the local MiniMax H3 reference-to-video model.

Python standard library only. A clip is described by a JSON spec; the ComfyUI
API graph is built here, so no exported workflow file is needed.

    python presenter.py render --spec workflows/specs/test-a1.json
    python presenter.py render --spec SPEC --set seed=7 --set seconds=15

Spec fields (paths are relative to the project folder):
    name            output folder name under runs/<group>/
    group           runs/ subfolder, default "renders"
    image           presenter reference image (<Picture 1>)
    prompt          H3 prompt; {line} is replaced by the "line" field
    line            exact words to be spoken (recorded in the manifest)
    seconds         clip length; rounded up to H3's 17k+5 frame grid
    width, height   generation size, multiples of 32 (default 480x864)
    turbo           4-step turbo LoRA (default true)
    seed            noise seed (default 1)
    anchor_image    pin the reference image as frame 0 (default true)
    narration       audio anchored as the soundtrack from frame 0 (route B)
    voice_ref       audio passed as <Audio 1> voice reference
    ref_image_size  "match" (fast) or "max" (identity fidelity, slower)
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parent
COMFY = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
FPS = 24
MODELS = {
    "unet": "minimax_h3_ref2va_pruned_int8_convrot.safetensors",
    "turbo_lora": "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors",
    "clip": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
    "video_vae": "minimax_h3_video_vae_fp16.safetensors",
    "audio_vae": "minimax_h3_audio_vae_fp32.safetensors",
}
DEFAULTS = {"group": "renders", "width": 480, "height": 864, "turbo": True, "seed": 1,
            "anchor_image": True, "ref_image_size": "match", "line": ""}


def frames_for(seconds):
    """H3 accepts 17k+5 frames; round up so the clip is never shorter than asked."""
    n = max(5, math.ceil(seconds * FPS))
    return n + (5 - n % 17) % 17


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def api(path, payload=None, raw=None, headers=None):
    data = raw if raw is not None else (None if payload is None else json.dumps(payload).encode())
    hdrs = dict(headers or {})
    if payload is not None:
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(COMFY + path, data=data, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            body = response.read()
    except urllib.error.HTTPError as err:
        raise SystemExit(f"ComfyUI {path} -> HTTP {err.code}: {err.read().decode(errors='replace')[:3000]}")
    return json.loads(body) if body[:1] in (b"{", b"[") else body


def upload(path):
    """Upload into ComfyUI's input folder under a content-hashed name, so reruns reuse it."""
    path = Path(path)
    name = f"rs_{sha256(path)[:12]}{path.suffix.lower()}"
    boundary = uuid.uuid4().hex
    parts = [f"--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n".encode(),
             (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\n"
              "Content-Type: application/octet-stream\r\n\r\n").encode() + path.read_bytes() + b"\r\n",
             f"--{boundary}--\r\n".encode()]
    api("/upload/image", raw=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    return name


def build_graph(spec, image_name, narration_name=None, voice_name=None):
    length = frames_for(spec["seconds"])
    g = {
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": MODELS["unet"], "weight_dtype": "default"}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": MODELS["clip"], "type": "minimax", "device": "default"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": MODELS["video_vae"]}},
        "avae": {"class_type": "VAELoader", "inputs": {"vae_name": MODELS["audio_vae"]}},
        "img": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "r2v": {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": {
            "clip": ["clip", 0], "vae": ["vae", 0], "audio_vae": ["avae", 0],
            "prompt": spec["prompt"].replace("{line}", spec["line"]),
            "width": spec["width"], "height": spec["height"], "length": length,
            "ref_image_size": spec["ref_image_size"], "ref_images.ref_image_0": ["img", 0]}},
    }
    model = ["unet", 0]
    if spec["turbo"]:
        g["lora"] = {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["unet", 0], "lora_name": MODELS["turbo_lora"], "strength_model": 1.0}}
        model = ["lora", 0]
    if voice_name:
        g["voice"] = {"class_type": "LoadAudio", "inputs": {"audio": voice_name}}
        g["r2v"]["inputs"]["ref_audios.ref_audio_0"] = ["voice", 0]
    positive = ["r2v", 0]
    if spec["anchor_image"] or narration_name:
        guide = {"positive": positive, "latent": ["r2v", 1], "frame_idx": 0,
                 "vae": ["vae", 0], "audio_vae": ["avae", 0]}
        if spec["anchor_image"]:
            guide["image"] = ["img", 0]
        if narration_name:
            g["narr"] = {"class_type": "LoadAudio", "inputs": {"audio": narration_name}}
            guide["audio"] = ["narr", 0]
        g["guide"] = {"class_type": "MiniMaxH3AddGuide", "inputs": guide}
        positive = ["guide", 0]
    g.update({
        "noise": {"class_type": "RandomNoise", "inputs": {"noise_seed": spec["seed"]}},
        "guider": {"class_type": "BasicGuider", "inputs": {"model": model, "conditioning": positive}},
        "sampler": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "sigmas": {"class_type": "BasicScheduler", "inputs": {
            "model": ["unet", 0], "scheduler": "simple", "steps": 4 if spec["turbo"] else 20, "denoise": 1.0}},
        "sample": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["noise", 0], "guider": ["guider", 0], "sampler": ["sampler", 0],
            "sigmas": ["sigmas", 0], "latent_image": ["r2v", 1]}},
        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["sample", 0], "vae": ["vae", 0]}},
        "decode_audio": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["sample", 0], "vae": ["avae", 0]}},
        "video": {"class_type": "CreateVideo", "inputs": {"images": ["decode", 0], "audio": ["decode_audio", 0], "fps": FPS}},
        "save": {"class_type": "SaveVideo", "inputs": {
            "video": ["video", 0], "filename_prefix": f"rogue_signal/{spec['name']}", "format": "auto", "codec": "auto"}},
    })
    return g, length


def wait(prompt_id, timeout):
    start = time.time()
    while time.time() - start < timeout:
        history = api(f"/history/{prompt_id}")
        if prompt_id in history:
            entry = history[prompt_id]
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                errors = [m for m in status.get("messages", []) if m[0] == "execution_error"]
                raise SystemExit(f"Render failed: {json.dumps(errors, indent=2)[:3000]}")
            return entry
        time.sleep(5)
    raise SystemExit(f"Timed out after {timeout}s; job {prompt_id} may still be running in ComfyUI.")


def render(spec, timeout):
    spec = {**DEFAULTS, **spec}
    out = ROOT / "runs" / spec["group"] / spec["name"]
    out.mkdir(parents=True, exist_ok=True)
    inputs = {k: ROOT / spec[k] for k in ("image", "narration", "voice_ref") if spec.get(k)}
    names = {k: upload(p) for k, p in inputs.items()}
    graph, length = build_graph(spec, names["image"], names.get("narration"), names.get("voice_ref"))
    (out / "api-graph.json").write_text(json.dumps(graph, indent=2), encoding="utf-8")
    started = time.time()
    queued = api("/prompt", {"prompt": graph, "client_id": "rogue-signal"})
    prompt_id = queued["prompt_id"]
    print(f"queued {spec['name']}: {prompt_id} ({length} frames, {spec['width']}x{spec['height']})", flush=True)
    entry = wait(prompt_id, timeout)
    elapsed = round(time.time() - started, 1)
    files = [f for o in entry["outputs"].values() for v in o.values() if isinstance(v, list)
             for f in v if isinstance(f, dict) and "filename" in f]
    if not files:
        raise SystemExit("Job finished without an output file.")
    f = files[0]
    query = urllib.parse.urlencode({"filename": f["filename"], "subfolder": f.get("subfolder", ""), "type": f.get("type", "output")})
    clip = out / "clip.mp4"
    clip.write_bytes(api(f"/view?{query}"))
    manifest = {
        "spec": spec, "frames": length, "fps": FPS, "seconds": round(length / FPS, 3),
        "prompt_id": prompt_id, "elapsed_seconds": elapsed, "comfy_output": f, "output": str(clip.relative_to(ROOT)),
        "output_sha256": sha256(clip), "models": {k: v for k, v in MODELS.items() if k != "turbo_lora" or spec["turbo"]},
        "inputs": {k: {"path": spec[k], "sha256": sha256(p), "comfy_name": names[k]} for k, p in inputs.items()},
        "rendered_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (out / "render-manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    if shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-vn", "-ac", "2", "-ar", "48000",
                        str(out / "audio.wav")], check=False)
    print(f"done {spec['name']} in {elapsed}s -> {clip}")
    return manifest


def parse_value(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("render")
    p.add_argument("--spec", required=True)
    p.add_argument("--set", action="append", default=[], help="override a spec field, e.g. seed=7")
    p.add_argument("--timeout", type=int, default=1800)
    p.add_argument("--skip-existing", action="store_true", help="skip if a render manifest already exists")
    args = parser.parse_args()
    spec = json.loads((ROOT / args.spec).read_text(encoding="utf-8"))
    for item in args.set:
        key, _, value = item.partition("=")
        spec[key] = parse_value(value)
    done = ROOT / "runs" / spec.get("group", DEFAULTS["group"]) / spec["name"] / "render-manifest.json"
    if args.skip_existing and done.exists():
        print(f"skip {spec['name']}: already rendered")
        return
    render(spec, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
