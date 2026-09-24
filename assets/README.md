# Presenter specification

Selected direction: original fictional photorealistic female presenter. See `../docs/BRAND.md`. Keep private reference images/audio under `assets/private/`.

| File | Use |
| --- | --- |
| `presenter-reference-01.png` | 941×1672 (9:16) main reference, medium shot. Used for clip A. |
| `presenter-reference-01-close.png` | Tighter crop of the same image, made with FFmpeg. Used for clip B to give the cut a shot change. H3 only partly follows the tighter framing. |
| `Rogue Signal Logo.png` | White logo, added in the edit. Not yet printed on the T-shirt; that image edit is still pending. |

## Voice

**Decided on 24 September 2026:** H3's own generated voice, a clear, warm female voice with a soft British accent, described in the prompt. Barry preferred it clearly over the free Windows text-to-speech voice tested with supplied narration. Lip sync was rated good in every clip. The voice held across the Episode 000 cut.

Voice consistency between episodes comes from the prompt description only. Passing a previous clip as a voice reference made H3 repeat that clip's words. The presenter's name is still undecided.

## Validated

- **Identity:** holds across 15-second clips at 480×864 and 768×1344.
- **Lip sync:** good (Barry's review).
- **Words:** exact, checked by `verify_speech.py`. One pronunciation slip ("experimont") happened in a draft and went away at 768×1344.
- **Minor:** her hands sometimes appear at the bottom of the frame in the first second.
