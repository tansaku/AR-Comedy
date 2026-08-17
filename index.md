---
layout: default
title: Sam Joseph — comedy
description: Stand-up comedy, Joke Wranglers podcast, Camden & Edinburgh 2026 — book for gigs and festivals.
image: /assets/images/camden-fringe-2026-poster.jpg
---

{% assign jw = site.data.highlights.joke_wranglers %}
{% assign cot = site.data.highlights.comedians_on %}

<section class="hero" aria-labelledby="hero-heading">
  <h1 id="hero-heading" class="hero-title">Sam Joseph</h1>
  <p class="hero-tagline">Comedian, parent, recovering tech person — midlife sold separately.</p>
  <p class="hero-lede">Stand-up on Japan, bilingual family life, and sharp tech jokes. <strong>Camden</strong> &amp; <strong>Edinburgh 2026</strong>: <em>I Think I’m Turning Japanese (I really think so, not!)</em> · Panel show podcast <strong><a href="{{ jw.spotify_url }}">Joke Wranglers</a></strong>.</p>
  <p class="hero-cred">Previously: solo show at Leicester, Brighton &amp; Tunbridge Wells Fringes; <strong>Comedy Booby Trap</strong> VR (313 episodes). Comedy nights with <strong>Hilarity Unlimited</strong>. Podcasts: <a href="{{ '/podcasts/' | relative_url }}">{{ cot.title }}</a> &amp; <a href="{{ jw.spotify_url }}">Joke Wranglers</a>.</p>
  <p class="hero-quote" role="note"><em>“Like a geek, grown up”</em> — Markus Birdman</p>
  <p class="hero-social">
    <a href="https://www.instagram.com/tansaku/">Instagram</a>
    <span class="sep" aria-hidden="true">·</span>
    <a href="https://www.facebook.com/tansaku">Facebook</a>
    <span class="sep" aria-hidden="true">·</span>
    <a href="{{ '/booking/' | relative_url }}">Book me</a>
  </p>
</section>

{% include home-showcase.html %}

## Upcoming gigs

{% include gigs-upcoming.html %}

<p class="gig-archive-link"><a href="{{ '/archive/' | relative_url }}">Full gig archive →</a></p>

## Impressions

<ul class="impressions-list" markdown="0">
  <li><em>“Superb”</em> — Pete Dickenson (scriptwriter and film-maker)</li>
  <li><em>“Very creative”</em> — George Tothill (Chortle Student Comedy Award finalist 2021)</li>
  <li><em>“Strangely watchable”</em> — Gordana Mićić (Groovie Comedy)</li>
  <li><em>“Like a geek, grown up”</em> — Markus Birdman (Britain's Got Talent finalist)</li>
  <li><em>“A breath of fresh air”</em> — Travis Booth-Millard (New Forest New Comedian finalist)</li>
  <li><em>“Hilarious”</em> — Beth Fox</li>
</ul>

## Podcasts

<p class="podcast-blurb" markdown="0">
  <strong class="podcast-title"><a href="{{ jw.spotify_url }}">Joke Wranglers</a></strong> — two teams of two comedians compete in 10 rounds of joke challenges.
  <br>
  <a href="{{ jw.spotify_url }}">Spotify</a>
  ·
  <a href="{{ jw.youtube_url }}">YouTube</a>
</p>

<p class="podcast-blurb" markdown="0">
  <strong class="podcast-title"><a href="{{ '/podcasts/' | relative_url }}">{{ cot.title }}</a></strong> — long-form chats with comedians.
  <br>
  <a href="{{ cot.spotify_url }}">Spotify</a>
  ·
  <a href="{{ cot.apple_url }}">Apple Podcasts</a>
  ·
  <a href="{{ cot.youtube_url }}">YouTube</a>
  ·
  <a href="{{ cot.rss_url }}">RSS</a>
</p>
