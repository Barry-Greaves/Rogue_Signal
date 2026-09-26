# Presenter production runbook

This is how one 30-second episode is rendered today. Each step is a single command, so Hermes, a scheduler or a person can run it. Keep a person in the loop for review while the trial is running.

Verified on 24 September 2026: Episode 000 was rendered end to end at production resolution, and both clips passed the word check.

## Requirements

- ComfyUI Desktop 0.37.0 running at `http://127.0.0.1:8188` (override with `COMFYUI_URL`), with the local MiniMax H3 models listed in `presenter.py` (`MODELS`).
- Python 3.10+ for `presenter.py`. It uses the standard library only.
- FFmpeg on `PATH`. It extracts `audio.wav` after each render and joins the clips.
- A separate Python environment for the word check, kept outside OneDrive:

```powershell
uv venv "$env:LOCALAPPDATA\RogueSignal\venv"
uv pip install --python "$env:LOCALAPPDATA\RogueSignal\venv\Scripts\python.exe" faster-whisper
```

The first run of the check downloads the `small.en` Whisper model (about 500 MB).

## Route

**H3 native voice (route A).** The presenter image is `<Picture 1>` and is pinned as frame 0. The exact line goes in the prompt inside a timeline. H3 generates the voice and the lip movement together. It was chosen over supplied narration (route B) because the H3 voice sounded far more natural than the free text-to-speech voice. Route B still works: set `narration` in a spec to lock a WAV as the soundtrack.

Do **not** pass an earlier clip as `voice_ref`. H3 speaks that clip's words, not just its voice.

## One clip

```powershell
python presenter.py render --spec workflows/specs/ep000-a.json --set name=ep000-a-768 --set width=768 --set height=1344 --timeout 3600
& "$env:LOCALAPPDATA\RogueSignal\venv\Scripts\python.exe" verify_speech.py runs/ep000/ep000-a-768
```

- `render` writes `clip.mp4`, `audio.wav`, `api-graph.json` and `render-manifest.json` (seed, models, input hashes, job ID, time taken) to `runs/<group>/<name>/`.
- `verify_speech.py` writes `speech-check.json` and exits with 1 if any word is missing, added or changed, or if there is speech after the last transcribed word. It can't hear mispronunciations, so a person still listens.
- `--skip-existing` skips a clip that already has a manifest, so a re-run after a crash or power cut only renders what's missing.
- Render **one clip at a time**. Show it, then start the next.

## Settings and measured times (RTX 5080 16 GB, 62 GB RAM, turbo 4-step)

| Use | Size | 15 s clip (362 frames) |
|---|---|---|
| Draft, to check words and pacing | 480×864 | about 3 minutes |
| Production | 768×1344 | about 14.6 minutes |

A full episode is two production clips, about 30 minutes of GPU time plus any re-renders. The 768×1344 output visibly reduces noise compared with the draft. Upscale to 1080×1920 in the edit.

## Script sizing

- About 32 words per 15-second clip fills the clip when the prompt asks for a "calm, measured pace" (about 2.25 words/s).
- If a line is noticeably shorter than the clip, H3 may repeat words to fill the time. The timeline prompt (`[0s-12s] says this line exactly once` / `[12s-15s] silent smile`) reduces this, and the word check catches it.
- Write numbers and names the way they should be spoken, for example "Rogue Signal AI", not "RogueSignalAI".

## Join: assemble.py (any number of clips)

```powershell
python assemble.py full  --clips runs/ep002/a runs/ep002/b runs/ep002/c --out runs/ep002/ep002-1080x1920.mp4
python assemble.py split --clips runs/ep002/a runs/ep002/b runs/ep002/c --panels p1.png p2.png p3.png p4.png p5.png p6.png --out runs/ep002/ep002-split.mp4
```

- **Trimming:** each clip is cut to exactly 15 s (H3 renders 362 frames, 15.083 s), so N clips give N × 15 s. The 3-clip test came out at 45.000 s, 1,080 frames.
- **full:** presenter full frame. 768×1344 is 4:7, so the script crops the largest 9:16 area (`--crop-y` sets the vertical offset) and scales it to 1080×1920 with Lanczos plus light sharpening.
- **split:** presenter panel 1080×1080 on top (a 992×992 square render passes through whole) and article panels 1080×840 below.
  - Panels are `file` or `file@start_seconds` and switch independently of the clip cuts. Without times they're spread evenly: 6 panels over 45 s is one every 7.5 s.
  - `--panel-scale 0.85` (the default) keeps article text clear of YouTube's right-hand buttons.
  - `--panel-top`, `--panel-x` and `--top-height` adjust the margins.
  - Keep key text in the top ~560 px of the panel. YouTube's title and channel name cover the bottom ~290 px of the frame.
- **Output:** H.264 CRF 16, AAC 48 kHz, `faststart`. `--dry-run` prints the FFmpeg command without running it.
- **Subtitles** are added afterwards with `captions.py` (`--margin-v 870` for the split layout).
- **Upscaling:** Lanczos doesn't add detail. An AI video upscaler (SeedVR2 nodes are built into ComfyUI 0.37; the model isn't downloaded) could be tested later.

## Not yet built

The logo, source and end-card overlays, article capture (headless Edge at 540 px × 2; manual for now), a single `episode` command covering every step, and YouTube upload.
