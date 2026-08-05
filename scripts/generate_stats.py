#!/usr/bin/env python3
"""
generate_stats.py

Fetches your total GitHub contributions and the languages used across your
repositories, then renders two SVG cards:

  - stats.svg  -> total contributions (all-time, via GraphQL)
  - langs.svg  -> top languages by bytes of code (via REST)

Environment variables required:
  GITHUB_TOKEN     - a GitHub personal access token
                      (classic PAT with "read:user" and "repo" scopes is safest;
                       a fine-grained token with "Read access to metadata and
                       contents" works for public repos too)
  GITHUB_USERNAME  - your GitHub username

Usage:
  pip install requests
  export GITHUB_TOKEN=ghp_xxx
  export GITHUB_USERNAME=your-username
  python scripts/generate_stats.py

Run this from the repo root (or point OUTPUT_DIR below) so stats.svg and
langs.svg land where your README expects them.
"""

import os
import sys
import datetime
import requests

GITHUB_API = "https://api.github.com"
GITHUB_GRAPHQL = "https://api.github.com/graphql"

# Where the SVGs get written. Default: repo root (current working directory).
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", ".")

# Concrete / fog / amber palette, matching the profile banner's aesthetic.
CONCRETE_950 = "#0d0e10"
CONCRETE_800 = "#232428"
CONCRETE_600 = "#3d3f45"
FOG_400 = "#8b9098"
FOG_100 = "#e7e9ec"
SIGNAL_AMBER = "#dcb27c"

# Every language bar renders in the same muted fog tone except the single
# top language, which gets the amber accent — one signal, kept rare.
DEFAULT_COLOR = FOG_400


def require_env(name):
    value = os.environ.get(name)
    if not value:
        print(f"ERROR: environment variable {name} is not set.", file=sys.stderr)
        sys.exit(1)
    return value


def get_session(token):
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "profile-stats-script",
    })
    return session


def get_account_created_year(session, username):
    resp = session.get(f"{GITHUB_API}/users/{username}")
    resp.raise_for_status()
    created_at = resp.json()["created_at"]  # e.g. "2015-03-02T12:00:00Z"
    return int(created_at[:4])


def get_total_contributions(session, username):
    """
    GraphQL's contributionsCollection only accepts windows of at most one
    year, so we sum year-by-year from account creation to today.
    """
    start_year = get_account_created_year(session, username)
    current_year = datetime.datetime.utcnow().year

    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
          }
        }
      }
    }
    """

    total = 0
    for year in range(start_year, current_year + 1):
        from_dt = f"{year}-01-01T00:00:00Z"
        # Clamp "to" so we don't request a future date beyond now.
        to_dt = min(
            datetime.datetime(year, 12, 31, 23, 59, 59),
            datetime.datetime.utcnow(),
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        variables = {"login": username, "from": from_dt, "to": to_dt}
        resp = session.post(
            GITHUB_GRAPHQL, json={"query": query, "variables": variables}
        )
        resp.raise_for_status()
        data = resp.json()

        if "errors" in data:
            print(f"GraphQL error for {year}: {data['errors']}", file=sys.stderr)
            continue

        user_data = data.get("data", {}).get("user")
        if not user_data:
            continue

        year_total = user_data["contributionsCollection"]["contributionCalendar"][
            "totalContributions"
        ]
        total += year_total

    return total


def get_all_owned_repos(session, username):
    repos = []
    page = 1
    while True:
        resp = session.get(
            f"{GITHUB_API}/users/{username}/repos",
            params={"per_page": 100, "page": page, "type": "owner"},
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return repos


def get_language_totals(session, username):
    repos = get_all_owned_repos(session, username)
    totals = {}

    for repo in repos:
        if repo.get("fork"):
            continue  # skip forked repos, they aren't "your" code

        full_name = repo["full_name"]
        resp = session.get(f"{GITHUB_API}/repos/{full_name}/languages")
        if resp.status_code != 200:
            continue
        for lang, byte_count in resp.json().items():
            totals[lang] = totals.get(lang, 0) + byte_count

    return totals


def generate_stats_svg(total_contributions, username, path):
    width, height = 420, 160
    svg = f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}"
     xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Total GitHub contributions">
  <defs>
    <linearGradient id="fog" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="{FOG_400}" stop-opacity="0"/>
      <stop offset="100%" stop-color="{FOG_400}" stop-opacity="0.18"/>
    </linearGradient>
  </defs>
  <style>
    .label {{ font: 600 11px 'JetBrains Mono','Courier New',monospace; fill: {FOG_400};
              letter-spacing: 3px; text-transform: uppercase; }}
    .stat  {{ font: 700 40px 'Archivo Black','Arial Narrow',Impact,sans-serif; fill: {FOG_100}; }}
    .sub   {{ font: 400 12px 'JetBrains Mono','Courier New',monospace; fill: {FOG_400};
              letter-spacing: 1px; }}
  </style>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}"
        fill="{CONCRETE_950}" stroke="{CONCRETE_600}"/>
  <rect x="0.5" y="0.5" width="140" height="{height - 1}" fill="url(#fog)"/>
  <rect x="0" y="0" width="4" height="{height}" fill="{SIGNAL_AMBER}"/>
  <text x="28" y="34" class="label">{username} // site log</text>
  <text x="28" y="98" class="stat">{total_contributions:,}</text>
  <text x="28" y="124" class="sub">total contributions — all time</text>
</svg>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)


def generate_langs_svg(language_totals, path, top_n=8):
    width = 420
    row_height = 30
    top_padding = 58
    bottom_padding = 22

    top_languages = sorted(
        language_totals.items(), key=lambda kv: kv[1], reverse=True
    )[:top_n]
    total_bytes = sum(v for _, v in top_languages) or 1

    height = top_padding + row_height * len(top_languages) + bottom_padding

    rows = []
    for i, (lang, byte_count) in enumerate(top_languages):
        pct = byte_count / total_bytes * 100
        # only the single top language gets the amber accent — everything
        # else stays a quiet, uniform fog grey (one signal, kept rare).
        color = SIGNAL_AMBER if i == 0 else DEFAULT_COLOR
        y = top_padding + i * row_height
        bar_max_width = 180
        bar_width = max(3, bar_max_width * (pct / 100))

        rows.append(f"""
  <text x="28" y="{y + 5}" class="lang">{lang.upper()}</text>
  <rect x="180" y="{y - 5}" width="{bar_max_width}" height="4" fill="{CONCRETE_600}"/>
  <rect x="180" y="{y - 5}" width="{bar_width:.1f}" height="4" fill="{color}"/>
  <text x="{width - 14}" y="{y + 5}" class="pct" text-anchor="end">{pct:.1f}%</text>""")

    svg = f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}"
     xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Most used languages">
  <style>
    .label {{ font: 600 11px 'JetBrains Mono','Courier New',monospace; fill: {FOG_400};
              letter-spacing: 3px; text-transform: uppercase; }}
    .lang  {{ font: 400 12px 'JetBrains Mono','Courier New',monospace; fill: {FOG_100};
              letter-spacing: 1px; }}
    .pct   {{ font: 400 11px 'JetBrains Mono','Courier New',monospace; fill: {FOG_400}; }}
  </style>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}"
        fill="{CONCRETE_950}" stroke="{CONCRETE_600}"/>
  <rect x="0" y="0" width="4" height="{height}" fill="{SIGNAL_AMBER}"/>
  <text x="28" y="34" class="label">structure // languages</text>
  {''.join(rows)}
</svg>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)


def main():
    token = require_env("GITHUB_TOKEN")
    username = require_env("GITHUB_USERNAME")

    session = get_session(token)

    print(f"Fetching total contributions for {username}...")
    total_contributions = get_total_contributions(session, username)
    print(f"  -> {total_contributions:,} total contributions")

    print(f"Fetching language breakdown for {username}'s repos...")
    language_totals = get_language_totals(session, username)
    print(f"  -> found {len(language_totals)} languages")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    stats_path = os.path.join(OUTPUT_DIR, "stats.svg")
    langs_path = os.path.join(OUTPUT_DIR, "langs.svg")

    generate_stats_svg(total_contributions, username, stats_path)
    generate_langs_svg(language_totals, langs_path)

    print(f"Wrote {stats_path}")
    print(f"Wrote {langs_path}")


if __name__ == "__main__":
    main()
