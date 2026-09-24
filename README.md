# Rogue Signal

A local-first pipeline for daily AI news videos, with optional Hermes orchestration, Claude writing/review, OpenAI text generation, and presenter clips rendered locally by MiniMax H3 in ComfyUI. 

**@RogueSignalAI · AI news. Human perspective.**

Target: one daily 30-second Short using two 15-second MiniMax H3 renders. See [brand identity](docs/BRAND.md) and the [production runbook](docs/PRODUCTION.md). The branding configuration is documentation and is not yet read by the generation code.

## Current capabilities

- **Speaking presenter clips.** `presenter.py` renders a 15-second clip of the presenter speaking an exact line, using the local MiniMax H3 model in ComfyUI. H3 generates the voice and lip sync together. Every render saves a manifest (seed, models, input hashes, job ID, time taken).
- **Word check.** `verify_speech.py` transcribes each clip with local Whisper and fails if a word is missing, added or changed.
- **Verified end to end.** On 24 September 2026, the Episode 000 launch draft was rendered as two 768×1344 clips, about 14.6 minutes each on an RTX 5080. Both passed the word check and were joined into an exact 30.000-second cut.
- **Research and drafting.** RSS/Atom collection with a rolling 24-hour UTC window, URL deduplication and per-feed failure reporting. Optional OpenAI or Claude script drafts.
- **Offline tests.** Standard-library tests cover research, graph building and the word check. No GPU is needed.

Not built yet: captions and overlays, a single command for a whole episode, scheduling and YouTube upload. No news episode has been produced; Episode 000 is an unpublished draft.

## Quick start

Requires Python 3.10+. The core scripts need no external packages. From this folder:

```powershell
python studio.py demo
python -m unittest discover -s tests -v
python studio.py research
python studio.py draft --sources runs/research-SUFFIX/sources.json
```

Every command creates a separate folder in `runs/`. The demo uses fictional, clearly labelled fixtures and makes no network calls. Research uses `config/feeds.json`; failures are saved in `feed-errors.json`. No eligible articles means the command fails rather than inventing news. Feed summaries are discovery evidence, not independently verified facts. Open the original reporting before approving a script.

For optional model calls, set `AI_PROVIDER` to `openai` or `claude`, `AI_MODEL` to an available model ID, and `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in the process environment. Otherwise drafts use an attributed template. These calls send the selected public source records to the configured provider. Model drafts require editorial review.

## Rendering the presenter

With ComfyUI running and the H3 models installed:

```powershell
python presenter.py render --spec workflows/specs/ep000-a.json --set width=768 --set height=1344
```

See [docs/PRODUCTION.md](docs/PRODUCTION.md) for the full sequence, measured render times, script sizing and the word check setup. ComfyUI defaults to `http://127.0.0.1:8188`; change `COMFYUI_URL` if necessary.

`studio.py comfy-submit --workflow FILE` and `comfy-status --prompt-id ID` still queue an arbitrary API-format graph unchanged and read its history.

## Project map

| Location | Purpose |
| --- | --- |
| `studio.py` | Research, drafting and generic ComfyUI commands |
| `presenter.py` | Render one presenter clip with local MiniMax H3 |
| `verify_speech.py` | Check that a clip speaks its line exactly (needs faster-whisper) |
| `config/` | Source list and brand settings |
| `prompts/` | Provider-neutral editorial instructions |
| `workflows/specs/` | Clip specs: presenter image, line, prompt, length |
| `assets/` | Presenter references, logo and asset notes |
| `docs/` | Brand, workflow, production runbook and episode drafts |
| `tests/` | Offline checks |
| `runs/` | Generated episode artifacts; excluded from version control |

## Design references

Provider adapters follow [OpenAI text generation](https://developers.openai.com/api/docs/guides/text) and [Claude Messages](https://platform.claude.com/docs/en/api/messages/create). ComfyUI submission follows its [official API example](https://github.com/Comfy-Org/ComfyUI/blob/master/script_examples/basic_api_example.py). The presenter graph is rebuilt from ComfyUI's bundled `video_minimax_h3_r2v` template. [Hermes Agent](https://github.com/NousResearch/hermes-agent) (v0.21.5 installed locally) is the intended orchestrator; it does not yet call these commands.

## Licence

Code is released under the [MIT licence](LICENSE). Model weights, the presenter reference and the logo are not covered by it; see `workflows/README.md` for model sources.
