# scripts/generate_stats.py
import requests
import pathlib
import datetime

USERNAME = "PrathamReddy888"   # change if needed

# --- Fetch basic profile info ---
user = requests.get(f"https://api.github.com/users/{USERNAME}").json()
repos = requests.get(f"https://api.github.com/users/{USERNAME}/repos").json()

stars = sum(r.get("stargazers_count", 0) for r in repos)
followers = user.get("followers", 0)
public_repos = user.get("public_repos", 0)

# --- Languages ---
langs = {}
for r in repos:
    lang = r.get("language")
    if lang:
        langs[lang] = langs.get(lang, 0) + 1
top_langs = sorted(langs.items(), key=lambda x: x[1], reverse=True)[:5]

# --- Contributions (via GitHub API events) ---
events = requests.get(f"https://api.github.com/users/{USERNAME}/events").json()
commit_days = set()
for e in events:
    if e.get("type") == "PushEvent":
        day = e["created_at"].split("T")[0]
        commit_days.add(day)

# Calculate streak
dates = sorted(commit_days)
streak = 0
max_streak = 0
last_date = None
for d in dates:
    dt = datetime.date.fromisoformat(d)
    if last_date and (dt - last_date).days == 1:
        streak += 1
    else:
        streak = 1
    max_streak = max(max_streak, streak)
    last_date = dt

# Yearly contributions (rough count)
this_year = datetime.date.today().year
year_commits = sum(1 for d in commit_days if datetime.date.fromisoformat(d).year == this_year)

# --- SVG helper ---
def make_svg(title, lines):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="500" height="180">
  <rect width="500" height="180" fill="white" stroke="black"/>
  <text x="250" y="30" font-size="20" text-anchor="middle" fill="black">{title}</text>
  {"".join(f'<text x="20" y="{60+i*25}" font-size="16" fill="black">{line}</text>' for i,line in enumerate(lines))}
</svg>"""

# --- Write SVGs ---
pathlib.Path("stats.svg").write_text(make_svg("GitHub Stats", [
    f"⭐ Stars: {stars}",
    f"👥 Followers: {followers}",
    f"📦 Public Repos: {public_repos}",
]))

pathlib.Path("langs.svg").write_text(make_svg("Top Languages", [
    f"{lang}: {count} repos" for lang, count in top_langs
]))

pathlib.Path("streak.svg").write_text(make_svg("Commit Streak", [
    f"🔥 Current Streak: {streak} days",
    f"🏆 Longest Streak: {max_streak} days",
]))

pathlib.Path("year.svg").write_text(make_svg("Yearly Contributions", [
    f"📅 {this_year}: {year_commits} commits",
]))

print("Generated stats.svg, streak.svg, langs.svg, year.svg")
