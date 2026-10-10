#!/usr/bin/env python3
"""
Builds the EmCurso organisation README for github.com/emcursopt.

GitHub renders an organisation's profile from `profile/README.md` in its public
`.github` repository. That Markdown is sanitised — no scripts, no stylesheets,
no inline styles — so everything that moves lives inside SVG files referenced
as images. An SVG loaded as an image keeps its own <style>, so CSS animations
inside it run; it just cannot reach the network.

That last point is why the text is outlines. An image-SVG cannot load a web
font, so live <text> would fall back to whatever the viewer's system has. As
paths it is identical everywhere. Each glyph is drawn once in <defs> and reused
with <use>, which keeps a card with a lot of text small.

Every card is written twice, dark and light, and the README picks one with
<picture> and prefers-color-scheme — the same arrangement as rqcramos/rqcramos.

    pip install -r scripts/requirements.txt
    python scripts/build.py            writes profile/README.md and profile/assets/
    python scripts/build.py --preview  then python scripts/preview.py, which writes
                                       scripts/.preview/preview.html (both themes)

To add a partner: add its SVG to scripts/logos and an entry to PARTNERS, run again.
"""

from __future__ import annotations

import base64
import json
import math
import os
import re
import sys
import urllib.request
from dataclasses import dataclass, field

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.svgLib.path import parse_path
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

HERE = os.path.dirname(os.path.abspath(__file__))  # scripts/
REPO = os.path.dirname(HERE)
FONTS = os.path.join(HERE, ".fonts")       # downloaded on first run, not committed
LOGOS = os.path.join(HERE, "logos")
GEOJSON = os.path.join(HERE, "data", "pt-adm1.geojson")  # copied from EmerPT src/data
OUT = os.path.join(REPO, "profile")
ASSETS = os.path.join(OUT, "assets")
PREVIEW = os.path.join(HERE, ".preview")   # local preview, not committed

# The fonts are OFL and fetched from Google Fonts' own repository rather than
# committed: they only matter to whoever regenerates the cards.
FONT_URLS = {
    "Inter-var.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf",
    "IBMPlexMono-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/ibmplexmono/IBMPlexMono-Regular.ttf",
    "IBMPlexMono-Medium.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/ibmplexmono/IBMPlexMono-Medium.ttf",
}


def ensure_fonts():
    os.makedirs(FONTS, exist_ok=True)
    for name, url in FONT_URLS.items():
        path = os.path.join(FONTS, name)
        if not os.path.exists(path):
            print("  a descarregar", name)
            urllib.request.urlretrieve(url, path)


ensure_fonts()

W = 1200  # every card is 1200 wide, like the personal profile's

# ── Palettes ────────────────────────────────────────────────────────────────
# The neutrals are the personal profile's (Apple-ish greys on near-black); the
# accent is EmCurso's own orange — the PWA's theme_color — darkened a step on
# white so it keeps its contrast.

DARK = dict(
    card="#0b0b0d", line="#1c1c20", line2="#2a2a2e", surface="#141417",
    text="#f5f5f7", muted="#a1a1a6", faint="#6e6e73", dots="#19191d",
    accent="#f97316", land="#121215", landline="#2a2a30",
)
LIGHT = dict(
    card="#ffffff", line="#e8e8ed", line2="#d2d2d7", surface="#f5f5f7",
    text="#1d1d1f", muted="#6e6e73", faint="#86868b", dots="#ececf0",
    accent="#ea580c", land="#f4f4f6", landline="#d2d2d7",
)

# ── Content ─────────────────────────────────────────────────────────────────
# Every figure here is checked against the codebase, not typed from memory:
# 18 mainland districts (src/data/pt-adm1.geojson), 3 sources (copy.ts SOURCES),
# 37 documented endpoints (the API home page, from the catalog), and 30 s for
# the /prociv/ refresh tier (api-center/cache-intervals.ts).

FIGURES = [
    ("18", "", "distritos\nmonitorizados"),
    ("3", "", "fontes\noficiais"),
    ("37", "", "endpoints\ndocumentados"),
    ("30", "s", "intervalo de\natualização"),
]

ECOSYSTEM = [
    ("Mapa", "Mapa em direto", "emcurso.pt",
     "Cada ocorrência da ANEPC no mapa, com estado e meios empenhados."),
    ("API", "API de dados abertos", "api.emcurso.pt",
     "37 endpoints em JSON e GeoJSON: ocorrências, meteorologia, incêndios, trânsito."),
    ("Estado", "Estado do serviço", "api.emcurso.pt/status",
     "Disponibilidade e latência de cada componente, medidas continuamente."),
    ("Alertas", "Notificações push", "emcurso.pt",
     "Notificações no browser e no telemóvel."),
]

# Wording taken from the API site's own SOURCES copy.
SOURCES = [
    ("ANEPC", "Autoridade Nacional de Emergência e Proteção Civil",
     "Ocorrências, meios empenhados e estado operacional."),
    ("IPMA", "Instituto Português do Mar e da Atmosfera",
     "Avisos, previsão e risco de incêndio rural."),
    ("ICNF", "Instituto da Conservação da Natureza e das Florestas",
     "Área ardida e histórico florestal, com índices FWI."),
]

# (label, [(name, core)]). Core items carry the accent dot, as in the profile.
STACK = [
    ("Interface", [("Next.js", True), ("React", True), ("TypeScript", True),
                   ("Tailwind CSS", False), ("MapLibre", False), ("Motion", False)]),
    ("Dados e serviços", [("PostgreSQL", True), ("Supabase", False), ("REST", False),
                          ("GeoJSON", False), ("Web Push", False), ("Resend", False)]),
    ("Operações", [("Cloudflare", True), ("Vercel", True), ("Workers AI", False),
                   ("AI Gateway", False)]),
]


# ── Typography ──────────────────────────────────────────────────────────────

def static_instance(src: str, axes: dict, name: str) -> str:
    """A static cut of a variable font, cached on disk."""
    os.makedirs(os.path.join(FONTS, "cache"), exist_ok=True)
    out = os.path.join(FONTS, "cache", name + ".ttf")
    if not os.path.exists(out):
        tt = TTFont(os.path.join(FONTS, src))
        instancer.instantiateVariableFont(tt, axes, inplace=True)
        tt.save(out)
    return out


@dataclass
class Face:
    key: str
    path: str
    tt: TTFont = field(init=False)
    upem: int = field(init=False)
    order: list = field(init=False)

    def __post_init__(self):
        self.tt = TTFont(self.path)
        self.upem = self.tt["head"].unitsPerEm
        self.order = self.tt.getGlyphOrder()
        self.glyphset = self.tt.getGlyphSet()
        self.hbfont = hb.Font(hb.Face(hb.Blob.from_file_path(self.path)))

    def shape(self, text: str):
        """Glyphs with kerning applied — a heavy headline without it looks loose."""
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hbfont, buf, {"kern": True, "liga": True})
        return [(self.order[i.codepoint], p.x_advance, p.x_offset, p.y_offset)
                for i, p in zip(buf.glyph_infos, buf.glyph_positions)]

    def outline(self, glyph: str) -> str:
        pen = SVGPathPen(self.glyphset)
        self.glyphset[glyph].draw(pen)
        return pen.getCommands()


DISPLAY = Face("d", static_instance("Inter-var.ttf", {"opsz": 32, "wght": 800}, "Inter-Display-800"))
TITLE = Face("t", static_instance("Inter-var.ttf", {"opsz": 32, "wght": 700}, "Inter-Display-700"))
SEMI = Face("s", static_instance("Inter-var.ttf", {"opsz": 14, "wght": 600}, "Inter-600"))
BODY = Face("b", static_instance("Inter-var.ttf", {"opsz": 14, "wght": 450}, "Inter-450"))
MONO = Face("m", os.path.join(FONTS, "IBMPlexMono-Regular.ttf"))
MONOM = Face("n", os.path.join(FONTS, "IBMPlexMono-Medium.ttf"))


# ── SVG document ────────────────────────────────────────────────────────────

CSS = """
.pop{transform-box:fill-box;transform-origin:center;animation:pop 700ms cubic-bezier(.16,1,.3,1) both}
.beat{transform-box:fill-box;transform-origin:center;animation:pop 600ms cubic-bezier(.16,1,.3,1) both,beat 1.6s ease-in-out 1.4s infinite}
.rise{animation:rise 1.1s cubic-bezier(.16,1,.3,1) both}
.fade{animation:fade 900ms ease both}
.draw{stroke-dasharray:1;animation:draw 2.6s cubic-bezier(.65,0,.35,1) both}
.ping{transform-box:fill-box;transform-origin:center;opacity:0;animation:ping 3.6s cubic-bezier(0,0,.2,1) infinite}
@keyframes pop{from{transform:scale(0);opacity:0}}
@keyframes beat{50%{transform:scale(1.45)}}
@keyframes rise{from{transform:translateY(28px);opacity:0}}
@keyframes fade{from{opacity:0}}
@keyframes draw{from{stroke-dashoffset:1}}
@keyframes ping{0%{transform:scale(1);opacity:.5}70%,100%{transform:scale(6);opacity:0}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}.ping{display:none}}
"""


def num(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s == "-0" else s


class Doc:
    """One SVG: a set of glyph defs, extra defs, extra CSS and the body."""

    def __init__(self, height: int, pal: dict, label: str):
        self.h = height
        self.pal = pal
        self.label = label
        self.glyphs: dict[tuple, str] = {}
        self.defs: list[str] = []
        self.css: list[str] = []
        self.body: list[str] = []

    def glyph(self, face: Face, name: str):
        key = (face.key, name)
        if key not in self.glyphs:
            d = face.outline(name)
            self.glyphs[key] = f"{face.key}{len(self.glyphs)}" if d else ""
            if d:
                self.defs.append(f'<path id="{self.glyphs[key]}" d="{d}"/>')
        return self.glyphs[key] or None

    def add(self, s: str):
        self.body.append(s)

    def svg(self) -> str:
        style = CSS + "".join(self.css)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{self.h}" '
            f'viewBox="0 0 {W} {self.h}" role="img" aria-label="{self.label}">'
            f"<style>{style}</style><defs>{''.join(self.defs)}</defs>{''.join(self.body)}</svg>"
        )


def measure(face: Face, text: str, size: float, tracking: float = 0.0) -> float:
    glyphs = face.shape(text)
    units = sum(g[1] for g in glyphs) + tracking * face.upem * max(len(glyphs) - 1, 0)
    return units * size / face.upem


def text(doc: Doc, face: Face, s: str, size: float, x: float, y: float, fill: str,
         tracking: float = 0.0, anchor: str = "start") -> tuple[str, float]:
    """A run of outlined text with its baseline at y. Returns (svg, width)."""
    glyphs = face.shape(s)
    scale = size / face.upem
    track = tracking * face.upem
    width = measure(face, s, size, tracking)
    if anchor == "middle":
        x -= width / 2
    elif anchor == "end":
        x -= width
    uses, pen = [], 0.0
    for name, adv, xo, yo in glyphs:
        gid = doc.glyph(face, name)
        if gid:
            uses.append(f'<use href="#{gid}" x="{num(pen + xo)}"' + (f' y="{num(yo)}"' if yo else "") + "/>")
        pen += adv + track
    svg = (f'<g transform="translate({num(x)} {num(y)}) scale({scale:.5f} {-scale:.5f})" '
           f'fill="{fill}">{"".join(uses)}</g>')
    return svg, width


def wrap(face: Face, s: str, size: float, max_w: float) -> list[str]:
    lines, line = [], ""
    for word in s.split():
        trial = (line + " " + word).strip()
        if line and measure(face, trial, size) > max_w:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    return lines


def anim(cls: str, inner: str, delay: float = 0.0) -> str:
    """Wrap so the CSS transform never replaces the run's own transform attribute."""
    style = f' style="animation-delay:{delay:.2f}s"' if delay else ""
    return f'<g class="{cls}"{style}>{inner}</g>'


def frame(doc: Doc, dots: bool = True):
    """The card: rounded, hairline border, a dotted texture fading to the edges."""
    p = doc.pal
    doc.defs.append(
        f'<pattern id="dp" width="18" height="18" patternUnits="userSpaceOnUse">'
        f'<circle cx="1.5" cy="1.5" r="1.1" fill="{p["dots"]}"/></pattern>'
        f'<radialGradient id="dg" cx="72%" cy="38%" r="70%"><stop offset="0" stop-color="#fff"/>'
        f'<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
        f'<mask id="dm"><rect width="{W}" height="{doc.h}" fill="url(#dg)"/></mask>'
        f'<clipPath id="cc"><rect x="1" y="1" width="{W - 2}" height="{doc.h - 2}" rx="26"/></clipPath>'
    )
    doc.add(f'<rect x="1" y="1" width="{W - 2}" height="{doc.h - 2}" rx="26" fill="{p["card"]}"/>')
    if dots:
        doc.add(f'<rect width="{W}" height="{doc.h}" fill="url(#dp)" mask="url(#dm)" clip-path="url(#cc)"/>')
    doc.add(f'<rect x="1" y="1" width="{W - 2}" height="{doc.h - 2}" rx="26" fill="none" '
            f'stroke="{p["line"]}" stroke-width="1.5"/>')


def legend(doc: Doc, label: str, x: float, y: float, anchor: str = "end", beat: bool = True,
           delay: float = 0.4):
    """`● LABEL` in mono — the profile's corner legend."""
    p = doc.pal
    run, w = text(doc, MONO, label.upper(), 12.5, 0, 0, p["faint"], tracking=0.14)
    start = x - w if anchor == "end" else x
    run, _ = text(doc, MONO, label.upper(), 12.5, start, y, p["faint"], tracking=0.14)
    dot = (f'<circle class="{"beat" if beat else "pop"}" style="animation-delay:{delay:.2f}s" '
           f'cx="{num(start - 13)}" cy="{num(y - 4.2)}" r="3.6" fill="{p["accent"]}"/>')
    doc.add(dot + anim("fade", run, delay))


def title(doc: Doc, s: str, x: float = 64, y: float = 118, delay: float = 0.0):
    run, _ = text(doc, TITLE, s, 50, x, y, doc.pal["text"], tracking=-0.04)
    doc.add(anim("rise", run, delay))


def rule(doc: Doc, y: float, x0: float = 64, x1: float = W - 64):
    doc.add(f'<path d="M{num(x0)} {num(y)}H{num(x1)}" stroke="{doc.pal["line"]}" stroke-width="1.2"/>')


# ── The EmCurso mark ────────────────────────────────────────────────────────

def mark(cx: float, cy: float, r: float, fill: str, hole: str) -> str:
    """The logo as geometry: a diamond with a diamond cut-out.

    Reconstructed rather than traced — public/logo-bimi.svg is a bitmap trace,
    soft at the edges; this is exact at any size. Proportions measured off that
    file: the hole's half-diagonal is 29% of the outer one, corners just eased.
    """
    def diamond(rr):
        return f"M{num(cx)} {num(cy - rr)}L{num(cx + rr)} {num(cy)}L{num(cx)} {num(cy + rr)}L{num(cx - rr)} {num(cy)}Z"
    return (f'<path d="{diamond(r)}" fill="{fill}" stroke="{fill}" stroke-width="{num(r * 0.16)}" '
            f'stroke-linejoin="round"/><path d="{diamond(r * 0.29)}" fill="{hole}"/>')


# ── Map of mainland Portugal ────────────────────────────────────────────────

def rdp(points, eps):
    """Ramer–Douglas–Peucker, so the outlines weigh kilobytes rather than megabytes."""
    if len(points) < 3:
        return points
    (x1, y1), (x2, y2) = points[0], points[-1]
    dx, dy = x2 - x1, y2 - y1
    norm = math.hypot(dx, dy) or 1e-9
    best, idx = 0.0, 0
    for i in range(1, len(points) - 1):
        px, py = points[i]
        dist = abs(dy * px - dx * py + x2 * y1 - y2 * x1) / norm
        if dist > best:
            best, idx = dist, i
    if best > eps:
        return rdp(points[: idx + 1], eps)[:-1] + rdp(points[idx:], eps)
    return [points[0], points[-1]]


def rdp_ring(ring, eps):
    """RDP for a closed ring.

    Plain RDP measures every point against the line from the first point to
    the last; on a closed ring those are the same point, every distance is
    zero, and the whole polygon collapses. Split at the vertex farthest from
    the start and simplify the two halves instead.
    """
    if ring[0] == ring[-1]:
        ring = ring[:-1]
    if len(ring) < 4:
        return ring
    sx, sy = ring[0]
    far = max(range(len(ring)), key=lambda i: (ring[i][0] - sx) ** 2 + (ring[i][1] - sy) ** 2)
    a = rdp(ring[: far + 1], eps)
    b = rdp(ring[far:] + [ring[0]], eps)
    return a[:-1] + b[:-1]


def load_map(x0: float, y0: float, height: float):
    """District outlines and centroids, projected into a box of the given height."""
    g = json.load(open(GEOJSON, encoding="utf-8"))
    feats = [f for f in g["features"] if not f["properties"]["shapeName"].startswith("Regi")]
    lat0 = math.radians(39.6)

    def polys(f):
        geom = f["geometry"]
        return [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]

    xs, ys = [], []
    for f in feats:
        for poly in polys(f):
            for lon, lat in poly[0]:
                xs.append(lon * math.cos(lat0))
                ys.append(-lat)
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    k = height / (maxy - miny)
    width = (maxx - minx) * k

    def proj(lon, lat):
        return (x0 + (lon * math.cos(lat0) - minx) * k, y0 + (-lat - miny) * k)

    districts = []
    for f in feats:
        paths, best_area, centroid = [], 0.0, None
        for poly in polys(f):
            ring = [proj(lon, lat) for lon, lat in poly[0]]
            simple = rdp_ring(ring, 0.45)
            if len(simple) < 4:
                continue
            paths.append("M" + "L".join(f"{num(x)} {num(y)}" for x, y in simple) + "Z")
            # Area-weighted centroid of the largest part (shoelace formula).
            a = cx = cy = 0.0
            for (xa, ya), (xb, yb) in zip(ring, ring[1:] + ring[:1]):
                c = xa * yb - xb * ya
                a += c
                cx += (xa + xb) * c
                cy += (ya + yb) * c
            if abs(a) > best_area:
                best_area, centroid = abs(a), (cx / (3 * a), cy / (3 * a))
        districts.append(("".join(paths), centroid))
    return districts, width


# ── Cards ───────────────────────────────────────────────────────────────────

def card_header(pal: dict) -> Doc:
    doc = Doc(520, pal, "EmCurso — proteção civil em tempo real. Mapa de Portugal continental com os 18 distritos monitorizados.")
    frame(doc)
    p = pal

    doc.add(anim("pop", mark(84, 82, 19, p["text"], p["card"])))
    legend(doc, "emcurso.pt", W - 64, 87)

    sub, _ = text(doc, SEMI, "Proteção civil em tempo real", 28, 64, 244, p["muted"], tracking=-0.012)
    doc.add(anim("fade", sub, 0.15))

    # The full stop is the font's own glyph in the accent — the profile's "rr."
    # does the same — placed where the tracked run would have put it.
    head, hw = text(doc, DISPLAY, "EmCurso", 168, 56, 402, p["text"], tracking=-0.042)
    stop, _ = text(doc, DISPLAY, ".", 168, 56 + hw - 0.042 * 168, 402, p["accent"])
    doc.add(anim("rise", head + stop, 0.25))

    status = "Em direto  ·  ANEPC  ·  IPMA  ·  ICNF"
    run, _ = text(doc, MONO, status.upper(), 13, 82, 458, p["faint"], tracking=0.14)
    doc.add(f'<circle class="beat" style="animation-delay:.9s" cx="68" cy="453.6" r="4" fill="{p["accent"]}"/>')
    doc.add(anim("fade", run, 0.9))

    # The map: outlines draw themselves in (the profile's signature move), the
    # land fills in behind them, then each district lights and starts to pulse.
    map_h = 372
    districts, map_w = load_map(0, 0, map_h)
    mx = W - 92 - map_w
    my = 112
    land = "".join(f'<path d="{d}"/>' for d, _ in districts)
    doc.add(f'<g transform="translate({num(mx)} {num(my)})">')
    doc.add(f'<g class="fade" style="animation-delay:1.1s;animation-duration:1.4s" fill="{p["land"]}">{land}</g>')
    for i, (d, _) in enumerate(districts):
        doc.add(f'<path class="draw" pathLength="1" d="{d}" fill="none" stroke="{p["landline"]}" '
                f'stroke-width="1.1" stroke-linejoin="round" style="animation-delay:{0.2 + i * 0.05:.2f}s"/>')
    for i, (_, (cx, cy)) in enumerate(districts):
        # Spread the pulses so no two districts beat together; deterministic,
        # so the file does not change between builds.
        ping_delay = 2.4 + (i * 1.37) % 3.6
        doc.add(f'<circle class="ping" cx="{num(cx)}" cy="{num(cy)}" r="3" fill="{p["accent"]}" '
                f'style="animation-delay:{ping_delay:.2f}s"/>')
        doc.add(f'<circle class="pop" cx="{num(cx)}" cy="{num(cy)}" r="3" fill="{p["accent"]}" '
                f'style="animation-delay:{1.7 + i * 0.06:.2f}s"/>')
    doc.add("</g>")

    cap, _ = text(doc, MONO, "18 DISTRITOS", 11.5, W - 64, 486, p["faint"], tracking=0.16, anchor="end")
    doc.add(anim("fade", cap, 2.4))
    return doc


def card_figures(pal: dict) -> Doc:
    doc = Doc(232, pal, "18 distritos monitorizados, 3 fontes oficiais, 37 endpoints documentados, 30 segundos de intervalo de atualização.")
    frame(doc, dots=False)
    p = pal
    col = (W - 128) / len(FIGURES)
    for i, (value, unit, label) in enumerate(FIGURES):
        x = 64 + i * col + (0 if i == 0 else 36)
        if i:
            doc.add(f'<path class="fade" style="animation-delay:{0.1 * i:.2f}s" d="M{num(64 + i * col)} 48V184" '
                    f'stroke="{p["line"]}" stroke-width="1.2"/>')
        big, bw = text(doc, DISPLAY, value, 76, x - 3, 122, p["text"], tracking=-0.032)
        extra = ""
        if unit:
            extra, _ = text(doc, SEMI, unit, 34, x - 3 + bw + 6, 122, p["muted"])
        doc.add(anim("rise", big + extra, 0.08 + i * 0.09))
        for j, line in enumerate(label.split("\n")):
            run, _ = text(doc, MONO, line.upper(), 11.5, x, 160 + j * 18, p["faint"], tracking=0.15)
            doc.add(anim("fade", run, 0.35 + i * 0.09))
    return doc


def card_ecosystem(pal: dict) -> Doc:
    rows_top, row_h = 168, 92
    doc = Doc(rows_top + row_h * len(ECOSYSTEM) + 44, pal,
              "O ecossistema: mapa em direto em emcurso.pt, API de dados abertos em api.emcurso.pt, estado do serviço e notificações push.")
    frame(doc)
    p = pal
    title(doc, "O ecossistema.")
    legend(doc, "Em produção", W - 64, 104)
    for i, (label, name, where, desc) in enumerate(ECOSYSTEM):
        y = rows_top + i * row_h
        rule(doc, y)
        d = 0.15 + i * 0.1
        lab, _ = text(doc, MONO, label.upper(), 12.5, 86, y + 52, p["faint"], tracking=0.15)
        doc.add(f'<circle class="pop" style="animation-delay:{d:.2f}s" cx="72" cy="{num(y + 47.8)}" r="3" fill="{p["accent"]}"/>')
        nm, _ = text(doc, SEMI, name, 22, 330, y + 42, p["text"], tracking=-0.012)
        ds, _ = text(doc, BODY, desc, 16.5, 330, y + 69, p["muted"])
        url, _ = text(doc, MONO, where, 13.5, W - 64, y + 42, p["faint"], anchor="end")
        doc.add(anim("fade", lab, d) + anim("rise", nm + ds, d) + anim("fade", url, d + 0.1))
    rule(doc, rows_top + row_h * len(ECOSYSTEM))
    return doc


def card_sources(pal: dict) -> Doc:
    doc = Doc(372, pal, "Fontes oficiais: ANEPC, IPMA e ICNF.")
    frame(doc)
    p = pal
    title(doc, "Fontes oficiais.")
    legend(doc, "Proveniência", W - 64, 104)
    col = (W - 128) / 3
    for i, (acr, name, emits) in enumerate(SOURCES):
        x = 64 + i * col + (0 if i == 0 else 32)
        d = 0.15 + i * 0.1
        if i:
            doc.add(f'<path class="fade" style="animation-delay:{d:.2f}s" d="M{num(64 + i * col)} 172V326" '
                    f'stroke="{p["line"]}" stroke-width="1.2"/>')
        big, _ = text(doc, MONOM, acr, 40, x - 2, 214, p["text"], tracking=-0.02)
        parts = [big]
        for j, line in enumerate(wrap(BODY, name, 15, col - 70)):
            run, _ = text(doc, BODY, line, 15, x, 250 + j * 21, p["muted"])
            parts.append(run)
        for j, line in enumerate(wrap(BODY, emits, 15, col - 70)):
            run, _ = text(doc, BODY, line, 15, x, 304 + j * 21, p["faint"])
            parts.append(run)
        doc.add(anim("rise", "".join(parts), d))
    return doc


def card_stack(pal: dict) -> Doc:
    rows_top, row_h = 168, 84
    doc = Doc(rows_top + row_h * len(STACK) + 44, pal,
              "Construído com Next.js, React e TypeScript na interface; PostgreSQL e Supabase nos dados; Cloudflare e Vercel nas operações.")
    frame(doc)
    p = pal
    title(doc, "Construído com.")
    legend(doc, "Núcleo", W - 64, 104, beat=False)
    for i, (label, items) in enumerate(STACK):
        y = rows_top + i * row_h
        rule(doc, y)
        lab, _ = text(doc, MONO, label.upper(), 12.5, 72, y + 47, p["faint"], tracking=0.15)
        doc.add(anim("fade", lab, 0.1 + i * 0.1))
        x = 330
        for j, (name, core) in enumerate(items):
            pad = 18
            tw = measure(SEMI, name, 16)
            dot_w = 16 if core else 0
            pw = tw + pad * 2 + dot_w
            parts = [f'<rect x="{num(x)}" y="{num(y + 21)}" width="{num(pw)}" height="42" rx="21" '
                     f'fill="{p["surface"]}" stroke="{p["line2"]}" stroke-width="1.2"/>']
            if core:
                parts.append(f'<circle cx="{num(x + pad + 3)}" cy="{num(y + 42)}" r="3.4" fill="{p["accent"]}"/>')
            run, _ = text(doc, SEMI, name, 16, x + pad + dot_w, y + 47.6, p["text"], tracking=-0.005)
            parts.append(run)
            doc.add(anim("pop", "".join(parts), 0.2 + i * 0.1 + j * 0.05))
            x += pw + 10
    rule(doc, rows_top + row_h * len(STACK))
    return doc


# ── Partners ────────────────────────────────────────────────────────────────

def logo_paths(file: str, keep=None):
    s = open(os.path.join(LOGOS, file), encoding="utf-8").read()
    out = []
    for m in re.finditer(r"<path([^>]*?)/?>", s):
        attrs = m.group(1)
        cls = re.search(r'class="([^"]+)"', attrs)
        if keep is not None and (not cls or cls.group(1) not in keep):
            continue
        d = re.search(r'\sd="([^"]+)"', attrs).group(1)
        rule_ = re.search(r'fill-rule="([^"]+)"', attrs)
        out.append((d, rule_.group(1) if rule_ else None))
    return out


def bounds(paths):
    pen = BoundsPen(None)
    for d, _ in paths:
        parse_path(d, pen)
    return pen.bounds


@dataclass
class Logo:
    name: str
    paths: list
    height: float          # rendered height of the artwork, px
    suffix: str = ""       # text set after the mark (the Impact Program)


PARTNERS = [
    Logo("Cloudflare", logo_paths("Cloudflare_Logo.svg", keep={"b", "c", "d"}), 40),
    Logo("Anthropic", logo_paths("Anthropic_logo.svg"), 14),
    Logo("Cloudflare Impact Program", logo_paths("Cloudflare_Logo.svg", keep={"b", "c"}), 19, "Impact Program"),
    Logo("ElevenLabs", logo_paths("ElevenLabs_Logo_01.svg"), 17),
]


def draw_logo(doc: Doc, logo: Logo, x: float, base: float, fill: str) -> tuple[str, float]:
    """A logo standing on `base` — every mark on one line, as on the site."""
    x0, y0, x1, y1 = bounds(logo.paths)
    k = logo.height / (y1 - y0)
    paths = "".join(f'<path d="{d}"' + (f' fill-rule="{r}"' if r else "") + "/>" for d, r in logo.paths)
    g = (f'<g transform="translate({num(x)} {num(base - logo.height)}) scale({k:.5f}) '
         f'translate({num(-x0)} {num(-y0)})" fill="{fill}">{paths}</g>')
    width = (x1 - x0) * k
    if logo.suffix:
        run, tw = text(doc, SEMI, logo.suffix, 16, x + width + 11, base, fill, tracking=-0.015)
        g += run
        width += 11 + tw
    return g, width


def card_partners(pal: dict) -> Doc:
    doc = Doc(232, pal, "Com o apoio de: " + ", ".join(l.name for l in PARTNERS) + ".")
    frame(doc, dots=False)
    p = pal
    cap, _ = text(doc, MONO, "COM O APOIO DE", 12, W / 2, 76, p["faint"], tracking=0.22, anchor="middle")
    doc.add(anim("fade", cap))

    base, gap = 154, 78
    one_set, cursor = [], 0.0
    for _ in range(2):  # two copies per set, so a short list still spans the card
        for logo in PARTNERS:
            g, w = draw_logo(doc, logo, cursor, base, p["muted"])
            one_set.append(g)
            cursor += w + gap
    set_w = cursor
    speed = 42  # px per second
    doc.css.append(
        f".mq{{animation:mq {set_w / speed:.1f}s linear infinite}}"
        f"@keyframes mq{{to{{transform:translateX(-{num(set_w)}px)}}}}"
    )
    doc.defs.append(
        f'<linearGradient id="fg" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        f'<stop offset=".14" stop-color="#fff"/><stop offset=".86" stop-color="#fff"/>'
        f'<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        f'<mask id="fm"><rect x="40" y="0" width="{W - 80}" height="{doc.h}" fill="url(#fg)"/></mask>'
    )
    track = "".join(one_set)
    doc.add(f'<g mask="url(#fm)"><g class="fade" style="animation-delay:.2s"><g class="mq">'
            f'<g transform="translate(40 0)">{track}<g transform="translate({num(set_w)} 0)">{track}</g></g>'
            f"</g></g></g>")
    return doc


# ── README ──────────────────────────────────────────────────────────────────

CARDS = {
    "header": (card_header, "EmCurso — proteção civil em tempo real", "https://emcurso.pt"),
    "figures": (card_figures, "18 distritos, 3 fontes oficiais, 37 endpoints, atualização a cada 30 segundos", None),
    "ecosystem": (card_ecosystem, "O ecossistema EmCurso: mapa, API, estado do serviço e notificações", None),
    "sources": (card_sources, "Fontes oficiais: ANEPC, IPMA e ICNF", None),
    "partners": (card_partners, "Com o apoio de Cloudflare, Anthropic, Cloudflare Impact Program e ElevenLabs", None),
}


def picture(name: str, alt: str, href: str | None) -> str:
    pic = (
        "<picture>\n"
        f'  <source media="(prefers-color-scheme: dark)" srcset="./assets/{name}-dark.svg" />\n'
        f'  <source media="(prefers-color-scheme: light)" srcset="./assets/{name}-light.svg" />\n'
        f'  <img src="./assets/{name}-dark.svg" alt="{alt}" width="100%" />\n'
        "</picture>"
    )
    return f'<a href="{href}">\n{pic}\n</a>' if href else pic


README_BODY = """
O **EmCurso** acompanha as ocorrências de proteção civil em Portugal à medida que acontecem. Reunimos o que a ANEPC, o IPMA e o ICNF publicam, normalizamos os dados e mostramo-los num mapa em direto — e numa API aberta, para quem quiser construir por cima.

É uma plataforma independente, feita para ser simples de usar, rápida e fiável. Porque é nos piores dias que mais gente precisa dela.

**[emcurso.pt](https://emcurso.pt)** &nbsp;·&nbsp; [api.emcurso.pt](https://api.emcurso.pt) &nbsp;·&nbsp; [Estado do serviço](https://api.emcurso.pt/status) &nbsp;·&nbsp; [Contacto](https://api.emcurso.pt/contacto) &nbsp;·&nbsp; [X](https://x.com/emcursopt)
""".strip()

README_FOOTER = """
<sub>Os dados de origem pertencem às autoridades que os publicam. O EmCurso não é um serviço oficial — **em caso de emergência, ligue 112.**</sub>
""".strip()


def build(preview: bool):
    os.makedirs(ASSETS, exist_ok=True)
    sizes = {}
    for name, (fn, _, _) in CARDS.items():
        for theme, pal in (("dark", DARK), ("light", LIGHT)):
            svg = fn(pal).svg()
            path = os.path.join(ASSETS, f"{name}-{theme}.svg")
            open(path, "w", encoding="utf-8").write(svg)
            sizes[f"{name}-{theme}"] = len(svg.encode("utf-8"))

    pics = {name: picture(name, alt, href) for name, (_, alt, href) in CARDS.items()}
    readme = "\n\n".join([
        pics["header"], "<br />", README_BODY, "<br />",
        pics["figures"], pics["ecosystem"], pics["sources"], pics["partners"],
        "<br />", README_FOOTER,
    ]) + "\n"
    open(os.path.join(OUT, "README.md"), "w", encoding="utf-8").write(readme)

    for k, v in sizes.items():
        print(f"  {k:18} {v / 1024:6.1f} KB")
    print(f"  total             {sum(sizes.values()) / 1024:6.1f} KB")
    if preview:
        write_preview()


def write_preview():
    """A local page that renders the README the way GitHub will: images, dark and light."""
    def uri(name, theme):
        data = open(os.path.join(ASSETS, f"{name}-{theme}.svg"), "rb").read()
        return "data:image/svg+xml;base64," + base64.b64encode(data).decode()
    imgs = {f"{n}-{t}": uri(n, t) for n in CARDS for t in ("dark", "light")}
    os.makedirs(PREVIEW, exist_ok=True)
    json.dump(imgs, open(os.path.join(PREVIEW, "images.json"), "w"))
    print("  images.json escrito")


if __name__ == "__main__":
    build(preview="--preview" in sys.argv)
