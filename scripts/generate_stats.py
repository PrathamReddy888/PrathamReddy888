# scripts/generate_stats.py
import requests
import pathlib

USERNAME = "PrathamReddy888"   # change if needed

# --- Fetch contributions (via GitHub API events) ---
events = requests.get(f"https://api.github.com/users/{USERNAME}/events").json()
commit_count = sum(1 for e in events if e.get("type") == "PushEvent")

# --- Fetch repos and languages ---
repos = requests.get(f"https://api.github.com/users/{USERNAME}/repos").json()
langs = {}
for r in repos:
    lang = r.get("language")
    if lang:
        langs[lang] = langs.get(lang, 0) + 1

# --- SVG helper ---
def make_svg(title, lines):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="500" height="180">
  <rect width="500" height="180" fill="white" stroke="black"/>
  <text x="250" y="30" font-size="20" text-anchor="middle" fill="black">{title}</text>
  {"".join(f'<text x="20" y="{60+i*25}" font-size="16" fill="black">{line}</text>' for i,line in enumerate(lines))}
</svg>"""

# --- Write SVGs ---
pathlib.Path("stats.svg").write_text(make_svg("Total Contributions", [
    f"📝 Commits (recent events): {commit_count}",
]))

pathlib.Path("langs.svg").write_text(make_svg("Languages Used", [
    f"{lang}: {count} repos" for lang, count in langs.items()
]))

print("Generated stats.svg and langs.svg")
