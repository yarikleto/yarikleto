"""Builds contrib-dark.svg and contrib-light.svg: the last year of GitHub contributions as an ASCII shade heatmap
in the same terminal window as the header.

Each day is one character cell shaded like the ASCII ramp  · ░ ▒ ▓ █  by GitHub's own contribution level.
The shades are drawn as patterns, not font glyphs, so the grid looks the same in every monospace font. Like the
header, the animation is SMIL with fill="freeze" and every element's base value is its final state.

    GITHUB_TOKEN=... python3 scripts/build-contrib.py [user]
"""
import json
import os
import subprocess
import sys
import urllib.request
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent

FONT = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'DejaVu Sans Mono', 'Liberation Mono', monospace"
W = 830
T = 5.0
FS, ADV = 13.5, 8.1
TERM_X, CMD_Y = 40, 66
GRID_X, GRID_Y = 72, 108               # top-left of the first day cell
CW, CH = 13.4, 15                      # one day = one character cell
LEVEL = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}

THEMES = {
    "dark": dict(bg="#0d1117", border="#30363d", bar="#161b22", title="#8b949e", cmd="#e6edf3", out="#c9d1d9",
                 dim="#8b949e", hl="#5CC8C8", prompt="#5CC8C8", empty="#30363d", shades=("#2D8A8A", "#44AAAA", "#5CC8C8", "#7fe0e0"),
                 scan="#ffffff"),
    "light": dict(bg="#ffffff", border="#d0d7de", bar="#f6f8fa", title="#57606a", cmd="#1f2328", out="#24292f",
                  dim="#6e7781", hl="#1a7f7f", prompt="#2D8A8A", empty="#d0d7de", shades=("#80cbc4", "#4db6ac", "#2D9F9F", "#1f6f6f"),
                  scan="#000000"),
}

QUERY = """query($login: String!) { user(login: $login) { contributionsCollection { contributionCalendar {
  totalContributions weeks { contributionDays { date contributionCount contributionLevel weekday } } } } } }"""


def token() -> str:
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()


def fetch(login: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token()}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.load(resp)
    if body.get("errors"):
        sys.exit(f"GitHub API error: {body['errors']}")
    return body["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def kt(t: float) -> str:
    return f"{min(max(t / T, 0), 1):.4f}"


def timeline(attr: str, points: list[tuple[float, float]], discrete: bool = False) -> str:
    pts = [(0.0, points[0][1])] + [p for p in points if p[0] > 0]
    if pts[-1][0] < T:
        pts.append((T, pts[-1][1]))
    mode = ' calcMode="discrete"' if discrete else ""
    return (f'<animate attributeName="{attr}" dur="{T}s" begin="0s" fill="freeze"{mode} '
            f'keyTimes="{";".join(kt(t) for t, _ in pts)}" values="{";".join(f"{v:g}" for _, v in pts)}"/>')


def shade_patterns(theme: dict) -> str:
    """░ ▒ ▓ as dot patterns of rising density; █ is a solid fill."""
    out = []
    for lvl, (step, size) in enumerate([(3.4, 1.1), (2.4, 1.2), (1.8, 1.25)], start=1):
        c = theme["shades"][lvl - 1]
        out.append(f'<pattern id="s{lvl}" width="{step}" height="{step}" patternUnits="userSpaceOnUse">'
                   f'<rect width="{size}" height="{size}" fill="{c}"/>'
                   f'<rect x="{step / 2}" y="{step / 2}" width="{size}" height="{size}" fill="{c}"/></pattern>')
    return "".join(out)


def grid(cal: dict, theme: dict, t0: float) -> tuple[str, str, float]:
    weeks = cal["weeks"]
    cells, months = [], []
    last_month = None
    for col, week in enumerate(weeks):
        x = GRID_X + col * CW
        for day in week["contributionDays"]:
            y = GRID_Y + day["weekday"] * CH
            lvl = LEVEL[day["contributionLevel"]]
            if lvl == 0:
                cells.append(f'<rect x="{x + CW / 2 - 1:.2f}" y="{y + CH / 2 - 1:.2f}" width="2" height="2" fill="{theme["empty"]}"/>')
            else:
                fill = theme["shades"][3] if lvl == 4 else f"url(#s{lvl})"
                cells.append(f'<rect x="{x + 1.2:.2f}" y="{y + 1.5:.2f}" width="{CW - 2.4:.2f}" height="{CH - 3:.2f}" fill="{fill}"/>')
        first = date.fromisoformat(week["contributionDays"][0]["date"])
        if first.month != last_month and col < len(weeks) - 2:
            if last_month is not None or first.day <= 7:
                months.append(f'<text x="{x:.2f}" y="{GRID_Y - 8}" fill="{theme["dim"]}">{first.strftime("%b")}</text>')
            last_month = first.month
    width = len(weeks) * CW
    sweep = 1.4
    defs = (f'<clipPath id="sweep"><rect x="{GRID_X - 2}" y="{GRID_Y - 24}" height="{7 * CH + 28}" width="{width + 4:.2f}">'
            f'{timeline("width", [(0, 0), (t0, 0), (t0 + sweep, width + 4)])}</rect></clipPath>')
    days = "".join(f'<text x="{TERM_X}" y="{GRID_Y + d * CH + 11}" fill="{theme["dim"]}">{n}</text>'
                   for d, n in ((1, "Mon"), (3, "Wed"), (5, "Fri")))
    body = (f'<g font-size="11">{days}</g>'
            f'<g clip-path="url(#sweep)"><g font-size="11">{"".join(months)}</g>{"".join(cells)}</g>')
    return defs, body, t0 + sweep


def build(name: str, cal: dict) -> str:
    th = THEMES[name]
    cmd = "gh contributions --last-year --ascii"
    total = f'{cal["totalContributions"]:,}'
    summary_y = GRID_Y + 7 * CH + 30
    legend_y = summary_y
    h = summary_y + 30

    # type the command, sweep the grid in, then print the total
    t, reveal, cursor = 0.3, [(0, 0), (0.3, 2 * ADV)], [(0.3, TERM_X + 2 * ADV, CMD_Y - 12)]
    for k in range(1, len(cmd) + 1):
        t += 0.03
        reveal.append((t, (2 + k) * ADV))
        cursor.append((t, TERM_X + (2 + k) * ADV, CMD_Y - 12))
    grid_defs, grid_body, t = grid(cal, th, t + 0.25)
    summary = f"{total} contributions in the last year"
    sum_reveal = [(0, 0), (t + 0.1, 0), (t + 0.25, len(summary) * ADV + 6)]
    prompt_y = h - 4  # cursor parks after the summary line
    cursor.append((t + 0.4, TERM_X + len(summary) * ADV + ADV, summary_y - 12))
    assert t + 0.4 < T - 0.3, f"animation runs past T: {t + 0.4:.2f}s"

    legend = []
    lx = W - TERM_X - 5 * (CW + 4) - 6 * ADV
    legend.append(f'<text x="{lx - 5 * ADV:.2f}" y="{legend_y}" font-size="11" fill="{th["dim"]}">less</text>')
    for lvl in range(5):
        x = lx + lvl * (CW + 4)
        y = legend_y - 11
        if lvl == 0:
            legend.append(f'<rect x="{x + CW / 2 - 1:.2f}" y="{y + CH / 2 - 1:.2f}" width="2" height="2" fill="{th["empty"]}"/>')
        else:
            fill = th["shades"][3] if lvl == 4 else f"url(#s{lvl})"
            legend.append(f'<rect x="{x + 1.2:.2f}" y="{y + 1.5:.2f}" width="{CW - 2.4:.2f}" height="{CH - 3:.2f}" fill="{fill}"/>')
    legend.append(f'<text x="{lx + 5 * (CW + 4) + 4:.2f}" y="{legend_y}" font-size="11" fill="{th["dim"]}">more</text>')

    xs = [(c[0], c[1]) for c in cursor]
    ys = [(c[0], c[2]) for c in cursor]
    fx, fy = cursor[-1][1], cursor[-1][2]
    final_t = cursor[-1][0]
    alt = f"{total} GitHub contributions in the last year, drawn as an ASCII heatmap"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}" font-family="{FONT}">
<title>{escape(alt)}</title>
<defs>{shade_patterns(th)}{grid_defs}
<clipPath id="cmd"><rect x="{TERM_X - 2}" y="{CMD_Y - 15}" height="22" width="{reveal[-1][1] + 6:g}">{timeline("width", reveal, discrete=True)}</rect></clipPath>
<clipPath id="sum"><rect x="{TERM_X - 2}" y="{summary_y - 15}" height="22" width="{sum_reveal[-1][1]:g}">{timeline("width", sum_reveal)}</rect></clipPath>
<pattern id="scan" width="4" height="3" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="{th["scan"]}" opacity="0.025"/></pattern>
</defs>
<rect x="5" y="5" width="{W - 10}" height="{h - 10}" rx="10" fill="{th["bg"]}" stroke="{th["border"]}"/>
<path d="M5,37V15a10,10 0 0 1 10-10H{W - 15}a10,10 0 0 1 10,10V37Z" fill="{th["bar"]}"/>
<line x1="5" y1="37" x2="{W - 5}" y2="37" stroke="{th["border"]}"/>
<circle cx="25" cy="21" r="6" fill="#ff5f57"/><circle cx="45" cy="21" r="6" fill="#febc2e"/><circle cx="65" cy="21" r="6" fill="#28c840"/>
<text x="{W / 2}" y="25.5" text-anchor="middle" font-size="12.5" fill="{th["title"]}">yarik@leto: ~/activity</text>
<g font-size="{FS}">
<g clip-path="url(#cmd)"><text x="{TERM_X}" y="{CMD_Y}" textLength="{(len(cmd) + 2) * ADV:g}" lengthAdjust="spacing" xml:space="preserve"><tspan fill="{th["prompt"]}" font-weight="700">$</tspan> <tspan fill="{th["cmd"]}">{escape(cmd)}</tspan></text></g>
{grid_body}
<g clip-path="url(#sum)"><text x="{TERM_X}" y="{summary_y}" textLength="{len(summary) * ADV:g}" lengthAdjust="spacing" xml:space="preserve"><tspan fill="{th["hl"]}" font-weight="700">{escape(total)}</tspan><tspan fill="{th["out"]}"> contributions in the last year</tspan></text></g>
</g>
{"".join(legend)}
<rect x="{fx:g}" y="{fy:g}" width="{ADV:g}" height="16" rx="1" fill="{th["prompt"]}" opacity="0.85">{timeline("x", [(0, xs[0][1])] + xs, discrete=True)}{timeline("y", [(0, ys[0][1])] + ys, discrete=True)}<animate attributeName="opacity" begin="{final_t + 0.4:.2f}s" dur="1.1s" repeatCount="indefinite" calcMode="discrete" keyTimes="0;0.5" values="0.85;0"/></rect>
<rect x="6" y="38" width="{W - 12}" height="{h - 44}" fill="url(#scan)" pointer-events="none"/>
</svg>
"""


if __name__ == "__main__":
    login = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_USER", "yarikleto")
    cal = fetch(login)
    for theme in THEMES:
        (ROOT / f"contrib-{theme}.svg").write_text(build(theme, cal), encoding="utf-8")
        print(f"wrote contrib-{theme}.svg ({cal['totalContributions']} contributions)")
