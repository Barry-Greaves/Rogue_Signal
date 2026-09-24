# Rogue Signal website

Static project website. Edit `index.html` for content and `style.css` for appearance; images live in `assets/`. No build step or JavaScript dependencies are required.

## Preview locally

From the repository root:

```powershell
python -m http.server 8765 --directory website --bind 127.0.0.1
```

Open http://127.0.0.1:8765. Stop the server with Ctrl+C.

## Publishing

The deployable directory is `website/`. It can be served by a static hosting provider. Adding these files to GitHub does not enable website hosting; no live website deployment is configured here.

## Updating content

Update the episode block in `index.html` when a new Short is published, and keep the build-status section accurate. Source publication dates belong in episode records even when narration omits them.

The current page links to the Episode 000 launch trial, the YouTube channel and this repository. It contains no analytics or embedded YouTube player. Google Fonts load externally with local sans-serif fallbacks.

The supplied logo and fictional presenter artwork are not covered by the repository's MIT code licence. See the repository licence and asset notes before reusing them.
