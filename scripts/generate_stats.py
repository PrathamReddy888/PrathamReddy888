# scripts/generate_stats.py
import requests
import pathlib

USERNAME = "PrathamReddy888"   # <-- change if needed
API_URL = f"https://api.github.com/users/{USERNAME}"
REPOS_URL = f"https://api.github.com/users/{USERNAME}/repos"

# Fetch profile info
user = requests.get(API_URL).json()
repos = requests.get(REPOS_URL).json()

stars = sum(r.get("stargazers_count", 0) for r in repos)
followers = user.get("followers", 0)
public_repos = user.get("public_repos", 0)

# Collect languages (very basic count)
langs = {}
for r in repos:
    lang = r.get("language")
    if lang:
        langs[lang] = langs.get(lang, 0) + 1

top_langs = sorted(langs.items(), key=lambda x: x[1], reverse=True)[:5]

# SVG template
def make_svg(title, lines):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="500" height="150">
  <rect width="500" height="150" fill="lightyellow"/>
  <text x="250" y="30" font-size="20" text-anchor="middle" fill="black">{title}</text>
  {"".join(f'<text x="20" y="{60+i*25}" font-size="16" fill="black">{line}</text>' for i,line in enumerate(lines))}
</svg>"""

# Stats.svg
stats_lines = [
    f"⭐ Stars: {stars}",
    f"👥 Followers: {followers}",
    f"📦 Public Repos: {public_repos}",
]
pathlib.Path("stats.svg").write_text(make_svg("GitHub Stats", stats_lines))

# Streak.svg (placeholder streak info)
streak_lines = ["Streak tracking requires commit history", "Add later if needed"]
pathlib.Path("streak.svg").write_text(make_svg("Streak Stats", streak_lines))

# Langs.svg
lang_lines = [f"{lang}: {count} repos" for lang, count in top_langs]
pathlib.Path("langs.svg").write_text(make_svg("Top Languages", lang_lines))

# Year.svg (placeholder yearly info)
year_lines = ["Yearly stats not implemented", "Add commit history later"]
pathlib.Path("year.svg").write_text(make_svg("Yearly Stats", year_lines))

print("Generated stats.svg, streak.svg, langs.svg, year.svg")
