---
type: episode
episode_id: episode-000
status: published
duration_seconds: 30
tags: [episode, launch]
---

# Episode 000 - Introducing the Project

Introduce the daily Short experiment and point viewers to the public repository. Finalise only after the repository URL exists and the workflow shown has been demonstrated.

This is a mirror of the Obsidian note `Episodes/Episode 000 - Introducing the Project.md`, which also links the test history.

## Clip A — 0 to 15 seconds

**Spoken (as rendered):**

“This is Rogue Signal: one AI story, thirty seconds, and the sources behind it. I’m the AI presenter for an experiment built by Barry, exploring how agents can help produce daily news.”

**Visual plan:** Presenter in a clean vertical studio composition. Immediate on-screen question, then a small project-name overlay added in editing. No long logo intro.

## Clip B — 15 to 30 seconds

**Spoken (as rendered):**

“The plan combines research, human review, and two video renders. Barry is documenting the code, workflows, and lessons on GitHub. Follow the trial at Rogue Signal AI, and explore the project through our channel.”

"RogueSignalAI" is written as "Rogue Signal AI" so that it's spoken as three words.

**Visual plan:** Same presenter, voice, lighting and wardrobe, with a closer framing (`presenter-reference-01-close.png`). Add the real repository address in the editor. Do not ask the model to generate readable GitHub text.

## Render record (24 September 2026)

| Clip | Spec | Size | Render | Word check | Speech |
|---|---|---|---|---|---|
| A draft | `ep000-a` | 480×864 | 195 s | PASS | 0.46–14.69 s |
| B draft | `ep000-b` | 480×864 | 185 s | PASS | 0.00–14.72 s |
| **A** | `ep000-a`, 768×1344 | 768×1344 | 876 s | PASS | 0.30–14.66 s |
| **B** | `ep000-b`, 768×1344 | 768×1344 | 874 s | PASS | 0.18–14.68 s |

- Seed 1, turbo on, 362 frames per clip.
- The cut is in `runs/ep000/ep000-768-cut.mp4`: exactly 30.000 s, with each clip trimmed to 15.000 s.
- **Barry's review:**
  - The draft A said "experimont"; the 768×1344 version is correct.
  - Clip B was flawless.
  - Lip sync is good, the voice is consistent across the cut, and the noise is lower at 768×1344.
  - He's happy with the presenter and considers the format ready for stories.

## Repository reference

Actual GitHub URL: **https://github.com/Barry-Greaves/Rogue_Signal** (created 24 September 2026, MIT). YouTube channel: **https://www.youtube.com/@RogueSignalAI** (channel ID UCUg91teBlNebH1IkjlIVRbQ). Both links checked on 24 September 2026.

**On-screen call to action (decided):** show both links as text added in the edit, over the last seconds of clip B:

- `youtube.com/@RogueSignalAI`
- `github.com/Barry-Greaves/Rogue_Signal` Do not render placeholder URLs. Clip B says "on GitHub", so the repository must exist before publishing.

## Review

- [x] Final narration fits both 15-second windows without rushing.
- [x] Same presenter and voice across the cut.
- [x] Spoken words match the approved script.
- [x] Public repo exists and describes current capabilities honestly.
- [x] Call to action points to a tested, available link.
- [ ] Captions and URL are readable on a phone. **Not in the published version:** no burned-in captions or end card, so YouTube auto-captions only. Add both from the next episode.
- [x] Export is 30 seconds with no added intro/outro length.
- [x] Video and metadata approved for publication (Barry, 24 Sep 2026).

## Publication

- **Published:** 24 September 2026, https://www.youtube.com/shorts/bSLASWbmr1Y (confirmed public and attached to @RogueSignalAI).
- **Title:** Introducing Rogue Signal: one AI story, 30 seconds, sources included
- **File:** `runs/ep000/ep000-1080x1920.mp4`. 1080×1920, 30.000 s, 24 fps, H.264 + AAC 48 kHz, upscaled from the 768×1344 renders with Lanczos.
- **Disclosure:** the description names the AI-generated presenter and Barry as creator/editor. Barry was advised to set "Altered or synthetic content" to Yes.
- **Not included:** captions, logo, end-card links. Barry decided on 24 Sep that this video doesn't need them. The text layer (DM Sans subtle subtitles) starts with the next episode.
- **Note:** on upload, YouTube showed a "Congrats on 1,000 subs!" notification. It's almost certainly a glitch on a brand-new channel. Check the real count in YouTube Studio.
