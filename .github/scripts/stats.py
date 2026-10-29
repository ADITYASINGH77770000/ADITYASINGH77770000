"""Draws dist/stats.svg, the profile's "GitHub at a glance" card, from the GitHub API.

Runs in the profile workflow every day with the workflow's own token (standard
library only), so the card never depends on a third-party stats service.
Usage: GITHUB_TOKEN=... python .github/scripts/stats.py <user> <out.svg>
"""
import base64
import json
import os
import sys
import urllib.request
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

USER, OUT = sys.argv[1], Path(sys.argv[2])
TOKEN = os.environ.get("GITHUB_TOKEN", "")
HERE = Path(__file__).parent
# GitHub's own language colours.
COLOURS = {"Python": "#3572A5", "Jupyter Notebook": "#DA5B0B", "HTML": "#e34c26", "JavaScript": "#f1e05a",
           "TypeScript": "#3178c6", "CSS": "#663399", "Java": "#b07219", "C++": "#f34b7d", "Shell": "#89e051"}


def api(path, body=None):
    req = urllib.request.Request("https://api.github.com" + path, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json",
                                          "User-Agent": "profile-stats"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


user = api(f"/users/{USER}")
repos = []
page = 1
while True:
    batch = api(f"/users/{USER}/repos?per_page=100&type=owner&page={page}")
    repos += batch
    if len(batch) < 100:
        break
    page += 1
own = [r for r in repos if not r["fork"] and r["name"] != USER]
stars = sum(r["stargazers_count"] for r in own)
langs = Counter(r["language"] for r in own if r["language"])
top = langs.most_common(5)
cc = api("/graphql", {"query": 'query($u:String!){user(login:$u){contributionsCollection{totalCommitContributions '
                               'contributionCalendar{totalContributions}}}}', "variables": {"u": USER}})
coll = cc["data"]["user"]["contributionsCollection"]
tiles = [(coll["contributionCalendar"]["totalContributions"], "contributions", "last 12 months"),
         (coll["totalCommitContributions"], "commits", "last 12 months"),
         (user["public_repos"], "public repos", "and counting"),
         (stars, "stars earned", "on my own repos")]


def font(weight):
    data = base64.b64encode((HERE / f"JetBrainsMono-{weight}.woff2").read_bytes()).decode()
    return f"@font-face{{font-family:'JB';font-weight:{weight};src:url(data:font/woff2;base64,{data}) format('woff2');}}"


W, H = 900, 236
parts = []
for i, (num, label, sub) in enumerate(tiles):
    x = 28 + (i % 2) * 210
    y = 70 + (i // 2) * 78
    d = 0.15 + i * 0.12
    parts.append(f'<g class="rise" style="animation-delay:{d:.2f}s"><text x="{x}" y="{y + 30}" class="num">{num}</text>'
                 f'<text x="{x}" y="{y + 50}" class="lab">{escape(label)}</text>'
                 f'<text x="{x}" y="{y + 66}" class="sub">{escape(sub)}</text></g>')
total = sum(n for _, n in top) or 1
bx, bw = 500, 300
for i, (lang, n) in enumerate(top):
    y = 74 + i * 30
    w = max(6, bw * n / top[0][1])
    c = COLOURS.get(lang, "#8b949e")
    d = 0.35 + i * 0.12
    parts.append(f'<text x="{bx}" y="{y}" class="lang">{escape(lang)}</text>'
                 f'<text x="{bx + bw + 72}" y="{y}" class="pct" text-anchor="end">{round(100 * n / total)}%</text>'
                 f'<rect x="{bx}" y="{y + 7}" width="{bw}" height="6" rx="3" fill="#21262d"/>'
                 f'<rect x="{bx}" y="{y + 7}" width="0" height="6" rx="3" fill="{c}">'
                 f'<animate attributeName="width" from="0" to="{w:.1f}" begin="{d:.2f}s" dur="0.9s" fill="freeze" calcMode="spline" keySplines="0.2 0.8 0.2 1" keyTimes="0;1"/></rect>')

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub at a glance: {tiles[0][0]} contributions and {tiles[1][0]} commits in the last 12 months, {tiles[2][0]} public repositories, {tiles[3][0]} stars earned. Top languages by repository: {", ".join(f"{l} {n}" for l, n in top)}.">
<defs><linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="#8E2DE2"/><stop offset="1" stop-color="#2575FC"/></linearGradient></defs>
<style>{font(400)}{font(700)}
text{{font-family:'JB',Consolas,'Liberation Mono',monospace}}
.head{{font-size:13px;font-weight:700;letter-spacing:2px;fill:#a78bfa}}
.num{{font-size:30px;font-weight:700;fill:url(#g)}}
.lab{{font-size:13px;font-weight:700;fill:#e6edf3}}
.sub{{font-size:11px;fill:#8b949e}}
.lang{{font-size:13px;fill:#e6edf3}}
.pct{{font-size:12px;fill:#8b949e}}
.rise{{opacity:0;animation:rise .7s cubic-bezier(.2,.8,.2,1) forwards}}
@keyframes rise{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:none}}}}
@media (prefers-reduced-motion:reduce){{.rise{{animation:none;opacity:1}}}}
</style>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="10" fill="#0d1117" stroke="#30363d"/>
<rect x="0.5" y="0.5" width="{W - 1}" height="4" rx="2" fill="url(#g)"/>
<text x="28" y="40" class="head">ACTIVITY</text>
<text x="{bx}" y="40" class="head">TOP LANGUAGES · BY REPO</text>
<line x1="462" y1="30" x2="462" y2="{H - 24}" stroke="#30363d"/>
{"".join(parts)}
</svg>
'''
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(svg, encoding="utf-8")
print(f"wrote {OUT}: tiles {[t[0] for t in tiles]}, languages {top}")
