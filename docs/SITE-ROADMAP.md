# Comedy site roadmap

Goals: visitors should **want to see the live show**, **book you for gigs and festivals**, and leave with a clear sense of **who you are and what you do**. This doc captures what is done, what is next, and longer-term ideas; nothing here blocks the current static site.

---

## Status (baseline shipped — Apr 2026)

| Area | What’s live |
|------|----------------|
| **Posters** | Brighton + VR PNGs in `assets/images/`; `_includes/home-showcase.html` (posters once, then text; Edinburgh full-width). |
| **Booking** | `/booking/` with booker-oriented copy; `site.booking_email` in `_config.yml`; nav + footer links. |
| **Hero / social** | Sam Joseph branding, tagline/cred/quote block, `image:` on key pages for sharing. |
| **Gigs** | `_data/gigs.yml`, upcoming + archive includes, reverse-chronological flow. |

---

## Near term (next you touch the site)

1. **Compress images** — keep PNGs under ~300–500KB where possible, or introduce WebP + `<picture>` if load time matters on mobile.
2. **Lock copy** — run the tagline / booker-blurb test (below); paste the winner into hero + expand `/booking/` if needed.
3. **Peer review** — five comic sites on phone: first screen + how they get booked; note 2–3 patterns to borrow.
4. **Edinburgh poster** — when you have art, add `poster` to that row in `highlights.yml` (same pattern as Brighton).

---

## 1. Show posters and imagery (ongoing)

**Assets**

- Brighton Fringe 2026 poster (Walrus Hideaway, dates, QR, branding).
- Comedy Booby Trap VR poster (Wed/Sat, 10:30pm UK, Scenic Club / Horizon).

**Still to consider**

- **Press / bookers:** higher-res or PDF one-sheet linked from `/booking/` or a future `/press/`.
- **Alt text + YAML** — keep dates and venues in data, not only in images (already the pattern).

---

## 2. Branding and tagline

**Today:** site leads with **Sam Joseph**, tagline territory, cred line, and a hero quote.

**To work through**

- **Stage vs legal name:** keep nav/footer aligned with posters (“Sam Joseph” — good).
- **Variants to test** (examples, not final):
  - Midlife / pivot: “Comedian. Parent. Recovering tech person.”
  - Japan / culture clash: short hook aligned with *Turning Japanese*.
  - VR + live: “Wednesdays and Saturdays in Horizon Worlds; the rest in real rooms.”

**Process**

1. Write **3–5 one-sentence taglines** + **one booker blurb** (50–80 words: credits, festivals, tone, tech/Japan, clean language).
2. Test with **two comedians + one non-comedy friend** — which line do they repeat back?
3. Lock **one hero line**; longer bio can move to **`/about/`** when you add it.

---

## 3. What strong comic sites tend to do (checklist)

| Pattern | Notes for this site |
|--------|---------------------|
| **One clear primary CTA** | Festival links + gig list + poster strip; keep “Book me” / booking visible early on mobile. |
| **Social proof above the fold** | Hero quote + impressions section; optional second quote if it doesn’t crowd the hero. |
| **Visible calendar** | YAML gigs + archive; booking email in footer. |
| **Show page per show** | Longer term: `/shows/turning-japanese/` etc. |
| **Low friction for bookers** | `/booking/` + future one-sheet PDF. |
| **Fast, mobile-first** | Static Jekyll is fine; image weight is the main lever. |

---

## 4. Career outcomes → site features

| Goal | Extension |
|------|-----------|
| **Sell tickets** | Posters + highlights + gig list stay prominent; update YAML as dates change. |
| **Get booked** | Enrich `/booking/` (sets, tech requirements, headshot link) as you get asked the same questions. |
| **Build audience** | Podcast + Instagram; optional Spotify embed if performance stays acceptable. |
| **Credibility** | Cred line under hero; optional logo strip later (festivals, press) without cluttering. |

---

## 5. Longer-term technical / structure

| Item | Why |
|------|-----|
| **`/about/`** | Photos, longer bio, booker-focused paragraph separate from festival urgency. |
| **`/shows/` collection** | One URL per hour (*Turning Japanese*, Booby Trap, future work) for SEO and sharing. |
| **Default OG/Twitter image in layout** | Site-wide fallback when a page has no `image:` (still use per-page `image:` for key URLs). |
| **Schema.org `Event`** | Rich results for festival rows (optional; validate and keep in sync with YAML). |
| **Newsletter** | Only if you will send; otherwise skip. |

---

## 6. Immediate next steps (queue)

See **Near term** above; ordered short list:

1. Image compression (or WebP).
2. Tagline/booker blurb iteration + paste into site.
3. Five-site peer review, jot findings in this doc or a scratch file.
4. Edinburgh `poster` when asset exists.

---

*Last updated: Apr 2026 — edit as the site evolves.*
