# Local generation workflow

Presenter clips don't use an exported workflow file. `presenter.py` builds the ComfyUI API graph in code from a small JSON spec in `specs/`. The graph follows ComfyUI's bundled `video_minimax_h3_r2v` template: the ref2va model, the 4-step turbo LoRA, and the presenter image as `<Picture 1>` pinned at frame 0 with `MiniMaxH3AddGuide`. The exact graph sent for each render is saved as `runs/<group>/<name>/api-graph.json`.

## Specs

| File | Purpose |
| --- | --- |
| `test-a1.json`, `test-a2.json` | 8 s speech tests, route A (H3 voice). A2 shows that `voice_ref` leaks words, so don't use it. |
| `test-b1.json`, `test-b2.json` | 8 s speech tests, route B (supplied narration pinned as the soundtrack) |
| `ep000-a.json`, `ep000-b.json` | Episode 000 launch clips, 15 s each. B uses the closer reference crop. |

Set `width`/`height` in the spec, or override on the command line (`--set width=768 --set height=1344`). The defaults are the 480×864 draft size.

## Models

These are loaded from ComfyUI's shared `models` folder and listed in `presenter.py` (`MODELS`). They aren't committed here.

- `minimax_h3_ref2va_pruned_int8_convrot.safetensors` (diffusion model)
- `minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors` (turbo LoRA)
- `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` (text encoder)
- `minimax_h3_video_vae_fp16.safetensors`, `minimax_h3_audio_vae_fp32.safetensors`

Download links are in the template's model notes ([Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3)). Their licences still need to be recorded before the public release.
