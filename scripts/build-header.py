"""Builds header-dark.svg and header-light.svg: an animated ASCII terminal header for the profile README.

The big name is ANSI Shadow lettering drawn cell by cell (blocks as rects, box-drawing strokes as paths),
so the grid stays aligned whatever monospace font the viewer has. The animation is SMIL with fill="freeze"
and every element's base value is its final state, so a renderer without animation shows the finished frame.

    python3 scripts/build-header.py
"""
import math
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent

FONT = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'DejaVu Sans Mono', 'Liberation Mono', monospace"
W = 830
T = 7.0  # every timeline animation runs 0..T and freezes on its final value

LETTERS = {
    "Y": ["██╗   ██╗", "╚██╗ ██╔╝", " ╚████╔╝ ", "  ╚██╔╝  ", "   ██║   ", "   ╚═╝   "],
    "A": [" █████╗ ", "██╔══██╗", "███████║", "██╔══██║", "██║  ██║", "╚═╝  ╚═╝"],
    "R": ["██████╗ ", "██╔══██╗", "██████╔╝", "██╔══██╗", "██║  ██║", "╚═╝  ╚═╝"],
    "I": ["██╗", "██║", "██║", "██║", "██║", "╚═╝"],
    "K": ["██╗  ██╗", "██║ ██╔╝", "█████╔╝ ", "██╔═██╗ ", "██║  ██╗", "╚═╝  ╚═╝"],
    "L": ["██╗     ", "██║     ", "██║     ", "██║     ", "███████╗", "╚══════╝"],
    "E": ["███████╗", "██╔════╝", "█████╗  ", "██╔══╝  ", "███████╗", "╚══════╝"],
    "T": ["████████╗", "╚══██╔══╝", "   ██║   ", "   ██║   ", "   ██║   ", "   ╚═╝   "],
    "O": [" ██████╗ ", "██╔═══██╗", "██║   ██║", "██║   ██║", "╚██████╔╝", " ╚═════╝ "],
    " ": ["   "] * 6,
}

THEMES = {
    "dark": dict(bg="#0d1117", border="#30363d", bar="#161b22", title="#8b949e", block=("#2D8A8A", "#5CC8C8"),
                 shadow="#2f6b6b", cmd="#e6edf3", out="#c9d1d9", dim="#8b949e", hl="#5CC8C8", prompt="#5CC8C8",
                 rule="#21262d", scan="#ffffff"),
    "light": dict(bg="#ffffff", border="#d0d7de", bar="#f6f8fa", title="#57606a", block=("#1f6f6f", "#2D9F9F"),
                  shadow="#a7d3d3", cmd="#1f2328", out="#24292f", dim="#6e7781", hl="#1a7f7f", prompt="#2D8A8A",
                  rule="#eaeef2", scan="#000000"),
}

# Terminal transcript. ("cmd", text) is typed after a prompt; ("out", segments) prints at once.
LINES = [
    ("cmd", "whoami"),
    ("out", [("name", "Yaroslav Pakhaliuk"), ("dim", " (aka Yarik Leto)")]),
    ("cmd", "cat experience.log"),
    ("out", [("dim", "[wix] "), ("out", "built "), ("hl", "LLM tools"),
             ("out", " for PR review and developer support, grounded by a "), ("hl", "RAG pipeline")]),
    ("out", [("dim", "[wix] "), ("hl", "5+ years"), ("out", " on Server Infrastructure: serverless dev tools for "),
             ("hl", "1,000+"), ("out", " developers")]),
    ("out", [("dim", "[wix] "), ("out", "built the serverless console to run, manage and debug "), ("hl", "1,000+"),
             ("out", " apps")]),
    ("out", [("dim", "[wix] "), ("out", "local dev CLI cut the edit-test cycle from "), ("hl", "minutes to seconds")]),
    ("cmd", [("cmd", "ships --with "), ("hl", "claude-code codex cursor")]),
    ("cmd", "ls ~/open-source"),
    ("out", [("name", "claude-teacher-plugin"), ("dim", " ("), ("hl", "15"), ("star", " "), ("dim", ")   "),
             ("name", "claude-agent-teams"), ("dim", " ("), ("hl", "npm"), ("dim", ")   "),
             ("name", "claude-profile"), ("dim", " ("), ("hl", "444 tests"), ("dim", ")")]),
    ("prompt", ""),
]

# Layout
COL, ROW = 9, 18                       # ASCII-art cell size
ART_TOP = 62
TAG_Y = 198
TERM_X, TERM_Y, LINE_H = 40, 244, 22  # first terminal baseline
FS, ADV = 13.5, 8.1                    # terminal font size and the advance every line is fitted to (0.6em)
H = TERM_Y + (len(LINES) - 1) * LINE_H + 34


def kt(t: float) -> str:
    return f"{min(max(t / T, 0), 1):.4f}"


def timeline(attr: str, points: list[tuple[float, float]], discrete: bool = False) -> str:
    """SMIL animation over 0..T through (time, value) points, holding the first value from 0."""
    pts = [(0.0, points[0][1])] + [p for p in points if p[0] > 0]
    if pts[-1][0] < T:
        pts.append((T, pts[-1][1]))
    times = ";".join(kt(t) for t, _ in pts)
    values = ";".join(f"{v:g}" for _, v in pts)
    mode = ' calcMode="discrete"' if discrete else ""
    return (f'<animate attributeName="{attr}" dur="{T}s" begin="0s" fill="freeze"{mode} '
            f'keyTimes="{times}" values="{values}"/>')


def cell_path(ch: str, x: float, y: float) -> str:
    cx, cy, d = x + COL / 2, y + ROW / 2, 2.0
    l, r, t, b = x, x + COL, y, y + ROW
    shapes = {
        "═": f"M{l},{cy - d}H{r}M{l},{cy + d}H{r}",
        "║": f"M{cx - d},{t}V{b}M{cx + d},{t}V{b}",
        "╗": f"M{l},{cy - d}H{cx + d}V{b}M{l},{cy + d}H{cx - d}V{b}",
        "╔": f"M{r},{cy - d}H{cx - d}V{b}M{r},{cy + d}H{cx + d}V{b}",
        "╝": f"M{l},{cy + d}H{cx + d}V{t}M{l},{cy - d}H{cx - d}V{t}",
        "╚": f"M{r},{cy + d}H{cx - d}V{t}M{r},{cy - d}H{cx + d}V{t}",
    }
    return shapes[ch]


def art(theme: dict) -> tuple[str, str]:
    word = "YARIK LETO"
    # one blank column between letters keeps A, R, I and K from running together
    rows = [" ".join(LETTERS[c][i] for c in word) for i in range(6)]
    width = len(rows[0]) * COL
    x0 = (W - width) / 2
    defs, body = [], []
    for i, row in enumerate(rows):
        y = ART_TOP + i * ROW
        start = 0.15 + i * 0.08
        defs.append(f'<clipPath id="art{i}"><rect x="{x0 - 2:g}" y="{y - 1:g}" height="{ROW + 2:g}" width="{width + 4:g}">'
                    f'{timeline("width", [(0, 0), (start, 0), (start + 0.6, width + 4)])}</rect></clipPath>')
        rects, paths = [], []
        for j, ch in enumerate(row):
            x = x0 + j * COL
            if ch == "█":
                rects.append(f'<rect x="{x:g}" y="{y:g}" width="{COL + 0.4:g}" height="{ROW + 0.4:g}"/>')
            elif ch != " ":
                paths.append(cell_path(ch, x, y))
        body.append(f'<g clip-path="url(#art{i})"><g fill="url(#block)">{"".join(rects)}</g>'
                    f'<path d="{"".join(paths)}" fill="none" stroke="{theme["shadow"]}" stroke-width="1.3"/></g>')
    defs.append(f'<linearGradient id="block" gradientUnits="userSpaceOnUse" x1="{x0:g}" y1="0" x2="{x0 + width:g}" y2="0">'
                f'<stop offset="0" stop-color="{theme["block"][0]}"/><stop offset=".5" stop-color="{theme["block"][1]}"/>'
                f'<stop offset="1" stop-color="{theme["block"][0]}"/></linearGradient>')
    return "".join(defs), "".join(body)


def tspans(segments: list[tuple[str, str]], theme: dict) -> str:
    out = []
    for kind, text in segments:
        if kind == "star":  # a blank cell; star() draws the glyph, since font stars render tiny
            out.append(" ")
            continue
        color = {"name": theme["cmd"], "cmd": theme["cmd"], "hl": theme["hl"], "dim": theme["dim"],
                 "out": theme["out"]}[kind]
        weight = ' font-weight="700"' if kind in ("name", "hl") else ""
        out.append(f'<tspan fill="{color}"{weight}>{escape(text)}</tspan>')
    return "".join(out)


def stars(segments: list[tuple[str, str]], y: float, theme: dict) -> str:
    out, col = [], 0
    for kind, text in segments:
        if kind == "star":
            cx, cy, r = TERM_X + col * ADV + ADV / 2, y - 4.6, 5.2
            pts = " ".join(f"{cx + (r if i % 2 == 0 else r * 0.45) * math.sin(i * math.pi / 5):.2f},"
                           f"{cy - (r if i % 2 == 0 else r * 0.45) * math.cos(i * math.pi / 5):.2f}" for i in range(10))
            out.append(f'<polygon points="{pts}" fill="{theme["hl"]}"/>')
        col += len(text)
    return "".join(out)


def terminal(theme: dict) -> tuple[str, str, float]:
    defs, body = [], []
    t = 1.6                       # the first prompt appears after the name and tagline
    cursor = [(0, 0.0, 0.0)]      # (time, x, y) for the cursor's top-left
    for n, (kind, payload) in enumerate(LINES):
        y = TERM_Y + n * LINE_H
        extra = ""
        if kind == "out":
            text = "".join(s for _, s in payload)
            content = tspans(payload, theme)
            extra = stars(payload, y, theme)
            reveal = [(0, 0), (t, 0), (t + 0.12, len(text) * ADV + 6)]
            t += 0.16
        else:
            segments = [("cmd", payload)] if isinstance(payload, str) else payload
            typed = "".join(s for _, s in segments)
            text = "$ " + typed
            content = f'<tspan fill="{theme["prompt"]}" font-weight="700">$</tspan> {tspans(segments, theme)}'
            reveal = [(0, 0), (t, 2 * ADV)]
            cursor.append((t, TERM_X + 2 * ADV, y - 12))
            t += 0.2
            for k in range(1, len(typed) + 1):
                reveal.append((t, (2 + k) * ADV))
                cursor.append((t, TERM_X + (2 + k) * ADV, y - 12))
                t += 0.028
            t += 0.2
        assert len(text) * ADV < W - 2 * TERM_X, f"line too long: {text}"
        defs.append(f'<clipPath id="ln{n}"><rect x="{TERM_X - 2}" y="{y - 15}" height="{LINE_H}" '
                    f'width="{reveal[-1][1] + 6:g}">{timeline("width", reveal, discrete=kind != "out")}</rect></clipPath>')
        length = f' textLength="{len(text) * ADV:g}" lengthAdjust="spacing"' if text.strip() != "$" else ""
        body.append(f'<g clip-path="url(#ln{n})"><text x="{TERM_X}" y="{y}"{length} xml:space="preserve">{content}</text>'
                    f'{extra}</g>')
    final_t = cursor[-1][0]
    assert final_t < T - 0.3, f"animation runs past T: {final_t:.2f}s"
    xs = [(c[0], c[1]) for c in cursor[1:]]
    ys = [(c[0], c[2]) for c in cursor[1:]]
    first = cursor[1][0]
    fx, fy = cursor[-1][1], cursor[-1][2]
    body.append(
        f'<rect x="{fx:g}" y="{fy:g}" width="{ADV:g}" height="16" rx="1" fill="{theme["prompt"]}" opacity="0.85">'
        f'{timeline("x", [(0, xs[0][1])] + xs, discrete=True)}'
        f'{timeline("y", [(0, ys[0][1])] + ys, discrete=True)}'
        f'{timeline("opacity", [(0, 0), (first, 0.85)], discrete=True)}'
        f'<animate attributeName="opacity" begin="{final_t + 0.4:.2f}s" dur="1.1s" repeatCount="indefinite" '
        f'calcMode="discrete" keyTimes="0;0.5" values="0.85;0"/></rect>')
    return "".join(defs), "".join(body), final_t


def build(name: str) -> str:
    th = THEMES[name]
    art_defs, art_body = art(th)
    term_defs, term_body, _ = terminal(th)
    tagline = "Senior Full-Stack Engineer, ex-Wix"
    tag_anim = timeline("opacity", [(0, 0), (0.9, 0), (1.4, 1)])
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">
<title>Yaroslav Pakhaliuk (Yarik Leto), Senior Full-Stack Engineer, ex-Wix</title>
<defs>{art_defs}{term_defs}
<pattern id="scan" width="4" height="3" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="{th["scan"]}" opacity="0.025"/></pattern>
</defs>
<rect x="5" y="5" width="{W - 10}" height="{H - 10}" rx="10" fill="{th["bg"]}" stroke="{th["border"]}"/>
<path d="M5,37V15a10,10 0 0 1 10-10H{W - 15}a10,10 0 0 1 10,10V37Z" fill="{th["bar"]}"/>
<line x1="5" y1="37" x2="{W - 5}" y2="37" stroke="{th["border"]}"/>
<circle cx="25" cy="21" r="6" fill="#ff5f57"/><circle cx="45" cy="21" r="6" fill="#febc2e"/><circle cx="65" cy="21" r="6" fill="#28c840"/>
<text x="{W / 2}" y="25.5" text-anchor="middle" font-size="12.5" fill="{th["title"]}">yarik@leto: ~</text>
{art_body}
<text x="{W / 2}" y="{TAG_Y}" text-anchor="middle" font-size="15" font-weight="600" fill="{th["out"]}" opacity="1">{escape(tagline)}{tag_anim}</text>
<line x1="{TERM_X}" y1="{TAG_Y + 18}" x2="{W - TERM_X}" y2="{TAG_Y + 18}" stroke="{th["rule"]}"/>
<g font-size="{FS}">{term_body}</g>
<rect x="6" y="38" width="{W - 12}" height="{H - 44}" fill="url(#scan)" pointer-events="none"/>
</svg>
"""


if __name__ == "__main__":
    for theme in THEMES:
        (ROOT / f"header-{theme}.svg").write_text(build(theme), encoding="utf-8")
        print(f"wrote header-{theme}.svg")
