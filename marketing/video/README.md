# headroid explainer video

Animated explainer (55 s, beige theme) for LinkedIn and the README, rendered from HTML with headless Chromium and ffmpeg.

| File | Format |
|---|---|
| `headroid-explainer.mp4` / `.html` | portrait 1080×1350 (4:5, LinkedIn feed) |
| `headroid-explainer-landscape.mp4` / `.html` | landscape 1920×1080 (16:9) |

Open an `.html` file in a browser to watch it live. To re-render after editing (needs Python Playwright and ffmpeg):

```bash
python render.py
python render.py --page headroid-explainer-landscape.html --size 1920x1080
python render.py --stills 3 12 28   # a few PNG frames under stills/ for a quick check
```
