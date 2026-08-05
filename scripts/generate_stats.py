# scripts/generate_stats.py
import pathlib

# List of SVG filenames to generate
files = ["stats.svg", "streak.svg", "langs.svg", "year.svg"]

# Simple placeholder SVG content
svg_template = """<svg xmlns="http://www.w3.org/2000/svg" width="400" height="100">
  <rect width="400" height="100" fill="lightblue"/>
  <text x="200" y="55" font-size="20" text-anchor="middle" fill="black">{label}</text>
</svg>
"""

# Write each file
for name in files:
    label = name.replace(".svg", "").capitalize()
    pathlib.Path(name).write_text(svg_template.format(label=label))

print("Generated:", ", ".join(files))
