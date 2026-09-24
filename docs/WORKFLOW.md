# Implementation plan and handoff

## Proposed episode flow

Daily trigger → collect sources → select stories → verify claims against original pages → write script → review script → synthesize narration → generate presenter and B-roll in ComfyUI → assemble with captions → review episode → upload privately → publish.

Implemented: collection, drafts and production briefs, a standalone ComfyUI queue/history adapter, presenter clip rendering (`presenter.py`) and the word check (`verify_speech.py`). See [PRODUCTION.md](PRODUCTION.md). Narration synthesis is not needed, because H3 generates the voice. Captions, assembly as a single command, scheduling and upload are pending. The confirmed target is one 30-second Rogue Signal Short daily, assembled from two intended 15-second H3 renders. See [brand identity](BRAND.md).

## Agent responsibilities

| Role | Proposed implementation | Current status |
| --- | --- | --- |
| Coordinator | Hermes Agent, or this CLI called by a scheduler | Hermes integration pending |
| Researcher | Feed collector followed by source-page verification | Feeds implemented; page verification pending |
| Writer | Claude or OpenAI API; ChatGPT can also consume the source file manually | API adapters implemented, offline tested only |
| Editor | A second model reviews claim/source pairs, then user review | Prompt/checklist only |
| Producer | `presenter.py` + local MiniMax H3; `verify_speech.py` | Clip render and word check implemented and verified on Episode 000 |
| Publisher | YouTube OAuth upload and status tracking | Metadata draft only |

These are pipeline roles, not independently running agents yet. Hermes should invoke documented CLI commands and inspect exit codes/artifacts. Avoid inventing an integration command before checking the installed Hermes version. Claude and OpenAI can swap writer/editor responsibilities; retain a single writer initially to avoid unnecessary calls. Automated calls use provider API credentials; manual ChatGPT/Claude workflows can exchange the same files.

## Milestones

1. **Done (24 September 2026).** ComfyUI 0.37.0, local H3 ref2va + turbo LoRA, RTX 5080 16 GB, 62 GB RAM. A 15-second portrait clip takes about 3 minutes at 480×864 and about 14.6 minutes at 768×1344.
2. Run live research, review feed coverage and add original sources. Add article extraction, event clustering, provenance per claim and a persistent story ledger to prevent repetition across days.
3. Configure one model and produce an approved script. Add structured script segments, validation and a separate review pass. Track usage/cost and bounded retry behavior.
4. **Done.** Presenter clips with speech: script fields go into the graph, the job is polled with a timeout, outputs are downloaded, prompt IDs are kept in a manifest, and node errors are reported.
5. **Partly done.** A two-clip FFmpeg join to exactly 30.000 s works (command in PRODUCTION.md). Upscaling to 1080×1920 works too. Still to do: captions, overlays and a single `episode` command that verifies audio duration, captions, aspect ratio and the final playback. Store a manifest of models/assets used.
6. Add a daily schedule at a user-selected local time. Use one scheduler, a run lock, duplicate prevention, recovery checkpoints, spend limits and actionable failure notifications. No schedule is installed yet.
7. Add YouTube OAuth and private uploads first; keep video ID and content hash to avoid duplicate uploads. Check current YouTube upload, synthetic-media disclosure and monetization documentation before implementation. Public publishing is eventual work, not enabled here.
8. Prepare open-source release. **Repository created 24 September 2026: https://github.com/Barry-Greaves/Rogue_Signal (MIT).** Still to do: add CI and contribution instructions, document hardware/model setup and known limitations, and exclude credentials, private assets and downloaded weights.

## Acceptance criteria for the first complete episode

Every narrated claim is traceable to a reviewed source; dates are correct; the selected workflow runs on the actual GPU; narration and lips match; the video plays through with readable captions; title/description match the content; generated-media disclosure has been reviewed; a repeat run cannot create duplicate public uploads.
