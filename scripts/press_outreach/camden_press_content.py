#!/usr/bin/env python3
"""Camden Fringe press-release body copy (shared across outreach emails)."""

from __future__ import annotations

import html as html_lib

from campaigns import CAMDEN_FRINGE_PAGE, CAMDEN_PRESS_TICKETS_EMAIL, Campaign

AUDIENCE_QUOTES = [
    (
        "A very entertaining show. It's unusual for comedy to also be informative, but this one was. "
        "I learnt about Japan while having lots of laughs.",
        "Sydney May, winner of the Komedia Brighton New Comedy Award 2025 and Comedy Bloomers "
        "LGBTQ+ New Comedian of the Year",
    ),
    (
        "A positively riveting show to watch. It has intriguing stories and great observational humour "
        "about Japanese culture, all delivered from the ramblings of a madman gaijin. This show really "
        "does have something for everyone, and at the end, I do feel a bit more Japanese.",
        "Kofi, Brighton audience member",
    ),
    (
        "With some comedians it feels like an 'us and them' situation, but with Sam it's an 'us and us'. "
        "He makes the audience feel at home so the laughter reverberates easily around the room.",
        "Carol, Brighton audience member",
    ),
    (
        "Buckle up for a whirlwind tour through Japanese culture, language and dating culture, and the "
        "wonderfully unpredictable world inside Sam's pachinko-machine mind.",
        "Mike, Brighton audience member",
    ),
]


def build_camden_release_html(campaign: Campaign) -> str:
    quotes_html = "".join(
        f'<p><em>&ldquo;{html_lib.escape(quote)}&rdquo;</em><br>'
        f"— {html_lib.escape(attribution)}</p>"
        for quote, attribution in AUDIENCE_QUOTES
    )
    return f"""
    <p><strong>Press Release</strong></p>
    <p><strong>British comedian Sam Joseph brings culture-clash comedy
    <em>I Think I&rsquo;m Turning Japanese (I Really Think So, NOT!)</em>
    to Camden Fringe 2026</strong></p>
    <p>
      After six years living in Japan and more than twenty years navigating bilingual family life
      between Tokyo, Honolulu and the UK, Sam Joseph brings his show to Camden Fringe for audiences
      who have ever felt out of place, misunderstood, or completely lost in translation.
    </p>
    <p>
      <em>I Think I&rsquo;m Turning Japanese (I Really Think So, NOT!)</em> is a 50-minute stand-up
      show about culture clash, marriage, language learning and the increasingly suspicious possibility
      that, despite all evidence to the contrary, Sam may be slowly turning Japanese. The show grew out
      of years living between cultures; he has previewed it in Leicester, Brighton and Camden, with
      club dates in London, Tokyo and Osaka.
    </p>
    <p><strong>Audience feedback from Brighton previews:</strong></p>
    {quotes_html}
    <p>
      <strong>Performance:</strong> Wednesday 13 August 2026, 7:00pm<br>
      <strong>Venue:</strong> Museum of Comedy, The Undercroft, St George&rsquo;s Church,
      Bloomsbury Way, London WC1A 2SR<br>
      <strong>Duration:</strong> 50 mins · <strong>Tickets:</strong> &pound;10.25<br>
      <strong>Camden Fringe listing:</strong>
      <a href="{CAMDEN_FRINGE_PAGE}">camdenfringe.com</a><br>
      <strong>Book tickets:</strong>
      <a href="{campaign.tickets_url}">Museum of Comedy box office</a><br>
      <strong>Press tickets:</strong> {CAMDEN_PRESS_TICKETS_EMAIL}
    </p>
    <p>
      <strong>Web:</strong> <a href="https://comedy.neurogrid.com/">comedy.neurogrid.com</a>
    </p>
    """
