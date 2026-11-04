"""Render headroid-explainer.html to MP4 (or a few still frames) with headless Chromium + ffmpeg.

    python render.py                      # -> headroid-explainer.mp4 (portrait, 30 fps)
    python render.py --page headroid-explainer-landscape.html --size 1920x1080
    python render.py --stills 2 8 25 38   # -> stills/frame-<t>.png for a quick look
"""

import argparse
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--page", default="headroid-explainer.html")
    ap.add_argument("--size", default="1080x1350", help="WIDTHxHEIGHT")
    ap.add_argument("--out")
    ap.add_argument("--stills", type=float, nargs="*")
    args = ap.parse_args()
    width, height = (int(v) for v in args.size.split("x"))
    page_url = (HERE / args.page).as_uri() + "?render"
    if not args.out:
        args.out = str(HERE / (Path(args.page).stem + ".mp4"))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
        page.goto(page_url)
        page.wait_for_timeout(300)
        if args.stills is not None:
            out = HERE / "stills" / Path(args.page).stem
            out.mkdir(parents=True, exist_ok=True)
            for t in args.stills:
                page.evaluate(f"render({t})")
                page.screenshot(path=str(out / f"frame-{t:05.1f}.png"))
            browser.close()
            return

        duration = page.evaluate("DURATION")
        frames = int(duration * args.fps)
        ff = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(args.fps), "-i", "-",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "slow", "-movflags", "+faststart",
             args.out],
            stdin=subprocess.PIPE,
        )
        for i in range(frames):
            page.evaluate(f"render({i / args.fps})")
            ff.stdin.write(page.screenshot(type="png"))
        ff.stdin.close()
        ff.wait()
        browser.close()
        print(f"wrote {args.out} ({frames} frames)")


if __name__ == "__main__":
    main()
