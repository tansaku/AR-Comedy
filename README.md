# AR-Comedy

Public site: [comedy.neurogrid.com](https://comedy.neurogrid.com) (GitHub Pages + Jekyll, theme: `jekyll-theme-midnight`).

## Editing gigs

All gigs live in [`_data/gigs.yml`](_data/gigs.yml), **newest dates first** (add upcoming gigs near the **top**). Each entry has ISO `date` (`YYYY-MM-DD`), optional `show_url`, `role`, `schedule`, `venue`, `venue_map_url`, `notes`, and `kind` (`performed`, `booker`, `bringer`, or `cancelled`).

- **Home page** lists gigs whose date is **today or later**, excluding `cancelled`. That split is computed when the site is **built** (every push to GitHub), comparing against the build date—not in the visitor’s browser.
- **Archive** is everything with a date **before** build day: [comedy.neurogrid.com/archive/](https://comedy.neurogrid.com/archive/)

To refresh the upcoming list after dates pass, push any change (or an empty commit). For a hands-off weekly refresh, you can add a scheduled GitHub Action that makes an empty commit.

One-off migration from the old README list: `python3 scripts/migrate_readme_gigs_to_yaml.py` (rewrites `_data/gigs.yml` from the legacy README format if you still have it in `README.md`).

## Home highlights (festivals & VR)

Edit [`_data/highlights.yml`](_data/highlights.yml) for the Brighton/Edinburgh blurb and the repeating **Comedy Booby Trap (VR)** block. Optionally add rows under `festivals.shows` to mirror ticket links and dates on the site. The [Instagram bio](https://www.instagram.com/tansaku/) is still the first place you update; this stack does not pull from Instagram automatically (that would need a separate API or build step).

## Repo layout

- `index.md` — main page (highlights, gigs, impressions, podcast)
- `_data/highlights.yml` — festival copy + optional show list; recurring VR (Scenic Club) blurb
- `archive.md` — past gigs
- `podcasts.md` — listen links (Spotify, Apple, RSS); URL `/podcasts/`
- `assets/css/custom.css` — small style additions
- `_includes/gigs-upcoming.html`, `gigs-archive.html`, `gig-list-item.html`, `home-highlights.html` — gig rendering / home panels

Other HTML assets in the repo (set lists, etc.) are unchanged.

## Going live (GitHub Pages)

1. Commit the changes you care about (at minimum `_data/gigs.yml` or `_data/highlights.yml` when only those changed; include `index.md`, theme files, etc. when those change too).
2. Push to the branch that **GitHub Pages** is configured to use (often `main`).
3. On GitHub: **Settings → Pages** — confirm source is that branch and `/ (root)`.
4. After the push, the **Actions** tab may show a “pages build and deployment” run; when it’s green, [comedy.neurogrid.com](https://comedy.neurogrid.com) updates (often within a minute or two).
5. Hard-refresh the site if you still see an old version (browser cache).
