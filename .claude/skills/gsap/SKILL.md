---
name: gsap
description: GSAP animation for PyArena's vanilla-JS pixel UI — vendoring, CSP-safe usage, stepped eases, timelines, Flip for leaderboard/bracket reordering, ScrollTrigger, counters and celebrations, with reduced-motion fallbacks. Use when adding or reviewing any non-trivial animation (entrances, list reordering, bracket advances, number counters, podium reveals, page transitions).
---

# GSAP in PyArena

## Setup
- GSAP is **vendored**, never loaded from a CDN: `frontend/vendor/gsap/` with `gsap.min.js` (ESM build `esm/` or `dist/gsap.min.js` exposing `window.gsap` — prefer the ESM files from the npm tarball) plus only the plugins we use (`Flip`, `ScrollTrigger`, `TextPlugin` if needed). Pin the exact version, record sha256 and the license in `vendor/gsap/README.md`. Fetch the npm tarball inside a throwaway container (`node:20-alpine`, pinned).
- Load lazily with `import()` from a tiny wrapper `frontend/services/motion.js` that:
  - returns `null` when `matchMedia('(prefers-reduced-motion: reduce)').matches` (callers then apply the final state directly);
  - registers plugins once;
  - exposes helpers below. Pages must work fully if motion.js returns null or fails to load.
- **CSP:** GSAP writes `element.style` through the CSSOM — allowed by `style-src 'self'`. Never inject `<style>` tags or style attributes in HTML strings.

## Pixel feel
- Use stepped eases for the retro look: `ease: "steps(6)"` for pops and slides, `"steps(4)"` for blinks; reserve smooth eases (`power2.out`) only for camera-like moves on large surfaces.
- Prefer animating `transform`/`opacity` (`x`, `y`, `scale`, `autoAlpha`). Round positions to whole pixels: `snap: { x: 4, y: 4 }` (multiples of the 4 px grid).
- Durations short: 0.25–0.6 s for UI, ≤ 1.2 s for reveals; stagger 0.05–0.08 s.

## Recipes
- **Entrance:** `gsap.from(cards, { y: 16, autoAlpha: 0, ease: "steps(5)", duration: .4, stagger: .06 })`.
- **Number counter:** tween a plain object and write `textContent` with `Intl.NumberFormat` each update (`onUpdate`), `snap: { val: 1 }`.
- **Leaderboard / bracket reordering:** `Flip.getState(rows)` → mutate DOM → `Flip.from(state, { duration: .5, ease: "steps(6)", absolute: true })`. Highlight movers with a short `steps(2)` flash.
- **Bracket advance:** timeline that (1) flashes the group winner, (2) draws the connector (`scaleX` from 0 with `transformOrigin` on the start side, stepped), (3) pops the avatar into the next-round slot.
- **Podium reveal:** 3rd → 2nd → 1st, each block grows with `steps(8)`, medal drops and bobs, then the shared `celebrate()` overlay.
- **ScrollTrigger** (landing only): reveal sections once (`once: true`), never scrubbed parallax on mobile.

## Hygiene
- Keep timelines in a variable and `kill()` them when a view unmounts or re-renders (language switch, round change) — no leaks, no double animations.
- `gsap.context()` scoped to a view root; call `ctx.revert()` on unmount.
- Never block interaction: animated elements stay clickable or the final state is reachable instantly (skip on tap).
- Test with reduced motion on: everything must be readable and complete without GSAP.
