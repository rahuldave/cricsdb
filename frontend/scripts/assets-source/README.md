# Asset source + regen

HTML files that render the site's brand assets (favicon + OG card)
via a real browser so Fraunces's variable-font axes render
correctly. Fraunces has a `WONK` axis whose default (what CLI
SVG→PNG tools like `rsvg-convert` pick up) is the quirky cursive
ampersand, NOT the masthead glyph. Chrome's CSS font renderer
honours `font-variation-settings` properly and picks the same
glyph the site uses — matching what users see on the homepage.

## To regenerate

```bash
# Make sure the Vite dev server is NOT needed — these HTML files
# load Fraunces from Google Fonts directly.

# 1. Favicon (512×512) — the browser renders a 512×512 body with
#    a large italic Fraunces '&' on cream.
agent-browser open "file:///$(pwd)/frontend/scripts/assets-source/favicon.html"
agent-browser wait --load networkidle
sleep 2                # give Google Fonts a moment
agent-browser screenshot body frontend/public/icon-512.png

# 2. Downscale for the smaller icon sizes.
sips -z 192 192 frontend/public/icon-512.png --out frontend/public/icon-192.png
sips -z 180 180 frontend/public/icon-512.png --out frontend/public/apple-touch-icon.png

# 3. OG card (1200×630).
agent-browser open "file:///$(pwd)/frontend/scripts/assets-source/og-card.html"
agent-browser wait --load networkidle
sleep 2
agent-browser screenshot body frontend/public/og-card.png
```

## Why not rsvg-convert?

`rsvg-convert` ignores `font-variation-settings` on SVG `<text>`
elements — Cairo/Pango on macOS doesn't honour the CSS variable-
axis properties. The result renders with Fraunces's default WONK
variant (decorative swashes on the ampersand), which doesn't
match the masthead. Chrome respects the axes correctly.

## Editing

- Bump match / delivery counts in `og-card.html` when the corpus
  grows meaningfully (every few months).
- Keep the kicker in sync with `frontend/src/pages/Home.tsx`'s
  masthead `.kicker` line (same "Est. YYYY · A T20 Almanack" text).
- After editing, regenerate per the steps above and commit the
  PNGs alongside the HTML change.
