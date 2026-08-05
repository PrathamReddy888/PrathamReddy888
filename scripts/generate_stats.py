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

# Small color map for common languages (GitHub's linguist colors, abbreviated).
LANGUAGE_COLORS = {
    "Python": "#3572A5",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "Java": "#b07219",
    "Go": "#00ADD8",
    "Rust": "#dea584",
    "C": "#555555",
    "C++": "#f34b7d",
    "C#": "#178600",
    "Ruby": "#701516",
    "PHP": "#4F5D95",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "Shell": "#89e051",
    "Swift": "#F05138",
    "Kotlin": "#A97BFF",
    "Dart": "#00B4AB",
    "Jupyter Notebook": "#DA5B0B",
}
DEFAULT_COLOR = "#8b949e"


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
     xmlns="http://www.w3.org/2000/svg">
  <style>
    .title {{ font: 600 16px 'Segoe UI', sans-serif; fill: #58a6ff; }}
    .stat  {{ font: 700 34px 'Segoe UI', sans-serif; fill: #c9d1d9; }}
    .label {{ font: 400 13px 'Segoe UI', sans-serif; fill: #8b949e; }}
  </style>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10"
        fill="#0d1117" stroke="#30363d"/>
  <text x="25" y="35" class="title">{username}'s GitHub Stats</text>
  <text x="25" y="95" class="stat">{total_contributions:,}</text>
  <text x="25" y="120" class="label">Total Contributions (all-time)</text>
</svg>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)


def generate_langs_svg(language_totals, path, top_n=8):
    width = 420
    row_height = 28
    top_padding = 55
    bottom_padding = 20

    top_languages = sorted(
        language_totals.items(), key=lambda kv: kv[1], reverse=True
    )[:top_n]
    total_bytes = sum(v for _, v in top_languages) or 1

    height = top_padding + row_height * len(top_languages) + bottom_padding

    rows = []
    for i, (lang, byte_count) in enumerate(top_languages):
        pct = byte_count / total_bytes * 100
        color = LANGUAGE_COLORS.get(lang, DEFAULT_COLOR)
        y = top_padding + i * row_height
        bar_max_width = 220
        bar_width = max(4, bar_max_width * (pct / 100))

        rows.append(f"""
  <text x="25" y="{y + 14}" class="lang">{lang}</text>
  <rect x="150" y="{y + 2}" width="{bar_max_width}" height="10" rx="5" fill="#21262d"/>
  <rect x="150" y="{y + 2}" width="{bar_width:.1f}" height="10" rx="5" fill="{color}"/>
  <text x="150" y="{y - 4}" class="pct" text-anchor="start">{pct:.1f}%</text>""")

    svg = f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}"
     xmlns="http://www.w3.org/2000/svg">
  <style>
    .title {{ font: 600 16px 'Segoe UI', sans-serif; fill: #58a6ff; }}
    .lang  {{ font: 400 13px 'Segoe UI', sans-serif; fill: #c9d1d9; }}
    .pct   {{ font: 400 11px 'Segoe UI', sans-serif; fill: #8b949e; }}
  </style>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10"
        fill="#0d1117" stroke="#30363d"/>
  <text x="25" y="35" class="title">Most Used Languages</text>
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