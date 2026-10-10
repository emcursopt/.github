#!/usr/bin/env python3
"""Writes scripts/.preview/preview.html: the README as it will render, both themes, live animations.

Run `python scripts/build.py --preview` first; it writes the images this page embeds.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PREVIEW = os.path.join(HERE, ".preview")
imgs = json.load(open(os.path.join(PREVIEW, "images.json")))

CARDS = [
    ("header", "EmCurso — proteção civil em tempo real", "https://emcurso.pt"),
    ("figures", "18 distritos, 3 fontes oficiais, 37 endpoints, atualização a cada 30 segundos", None),
    ("ecosystem", "O ecossistema EmCurso: mapa, API, estado do serviço e notificações", None),
    ("sources", "Fontes oficiais: ANEPC, IPMA e ICNF", None),
    ("partners", "Com o apoio de Cloudflare, Anthropic, Cloudflare Impact Program e ElevenLabs", None),
]


def card(name, alt, href):
    img = (f'<img class="card" data-card="{name}" alt="{alt}" '
           f'src="{imgs[name + "-dark"]}" width="1200">')
    return f'<a href="{href}" target="_blank" rel="noopener">{img}</a>' if href else img


head_card = card(*CARDS[0])
rest = "\n".join(card(*c) for c in CARDS[1:])

html = f"""<title>EmCurso no GitHub</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: one column at the width GitHub gives a profile README, a slim control row above it.
   The page follows the viewer's theme; the stage below it follows the toggle, because it
   stands in for where the README will live, and that is the visitor's choice, not ours. */
:root {{
  --bg: #f3f3f5;
  --panel: #ffffff;
  --fg: #1d1d1f;
  --muted: #6e6e73;
  --line: #e2e2e7;
  --accent: #ea580c;
  --mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg: #060607; --panel: #0e0e10; --fg: #ececee; --muted: #9a9aa0; --line: #232327; --accent: #f97316;
    color-scheme: dark;
  }}
}}
:root[data-theme="dark"] {{
  --bg: #060607; --panel: #0e0e10; --fg: #ececee; --muted: #9a9aa0; --line: #232327; --accent: #f97316;
  color-scheme: dark;
}}

/* The stage's own palette: the two grounds a README is read on. */
.stage[data-mode="dark"]  {{ --s-bg: #0d1117; --s-fg: #e6edf3; --s-muted: #9198a1; --s-link: #4493f8; --s-line: #262c36; }}
.stage[data-mode="light"] {{ --s-bg: #ffffff; --s-fg: #1f2328; --s-muted: #59636e; --s-link: #0969da; --s-line: #d1d9e0; }}

* {{ box-sizing: border-box; }}
body {{ background: var(--bg); color: var(--fg); font-family: var(--sans); padding-inline: 16px; padding-block: 28px 56px; }}
.wrap {{ max-width: 1012px; margin-inline: auto; display: grid; gap: 18px; }}

.bar {{ display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 14px 24px; }}
.who {{ display: grid; gap: 4px; min-width: 0; }}
.eyebrow {{ font: 500 11px/1 var(--mono); letter-spacing: .16em; text-transform: uppercase; color: var(--muted);
  display: flex; align-items: center; gap: 8px; }}
.eyebrow::before {{ content: ""; width: 6px; height: 6px; border-radius: 50%; background: var(--accent); }}
.path {{ font: 400 15px/1.3 var(--mono); color: var(--fg); overflow-wrap: anywhere; }}
.path span {{ color: var(--muted); }}

.controls {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }}
.seg {{ display: inline-flex; padding: 3px; border: 1px solid var(--line); border-radius: 999px; background: var(--panel); }}
.seg button, .replay {{ font: 500 12px/1 var(--mono); letter-spacing: .06em; border: 0; cursor: pointer; color: var(--muted);
  background: transparent; padding: 8px 14px; border-radius: 999px; }}
.seg button[aria-pressed="true"] {{ background: var(--fg); color: var(--panel); }}
.replay {{ border: 1px solid var(--line); background: var(--panel); color: var(--fg); padding: 9px 14px; }}
.replay:hover {{ border-color: var(--muted); }}
button:focus-visible, a:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}

.stage {{ background: var(--s-bg); color: var(--s-fg); border: 1px solid var(--line); border-radius: 14px;
  padding: clamp(16px, 4vw, 40px); transition: background .25s ease, color .25s ease; }}
.readme {{ max-width: 830px; margin-inline: auto; font-size: 16px; line-height: 1.5; display: grid; gap: 16px; }}
.readme p {{ margin: 0; max-width: 72ch; }}
.readme a {{ color: var(--s-link); text-decoration: none; }}
.readme a:hover {{ text-decoration: underline; }}
.readme .links {{ display: flex; flex-wrap: wrap; gap: 4px 0; }}
.readme .links span {{ color: var(--s-muted); padding-inline: 8px; }}
.readme small {{ color: var(--s-muted); font-size: 12px; line-height: 1.5; }}
.readme small strong {{ color: var(--s-fg); }}
.card {{ display: block; width: 100%; height: auto; max-width: 100%; }}
.gap {{ height: 8px; }}

.note {{ font: 400 12.5px/1.6 var(--mono); color: var(--muted); max-width: 80ch; }}
@media (prefers-reduced-motion: reduce) {{ .stage {{ transition: none; }} }}
</style>

<div class="wrap">
  <header class="bar">
    <div class="who">
      <p class="eyebrow">Pré-visualização</p>
      <p class="path">emcursopt <span>/</span> .github <span>/</span> profile/README.md</p>
    </div>
    <div class="controls">
      <div class="seg" role="group" aria-label="Tema do README">
        <button type="button" id="mode-dark" data-mode="dark" aria-pressed="true">Escuro</button>
        <button type="button" id="mode-light" data-mode="light" aria-pressed="false">Claro</button>
      </div>
      <button type="button" class="replay" id="replay">Repetir animações</button>
    </div>
  </header>

  <main class="stage" id="stage" data-mode="dark">
    <article class="readme">
      {head_card}
      <div class="gap"></div>
      <p>O <strong>EmCurso</strong> acompanha as ocorrências de proteção civil em Portugal à medida que acontecem. Reunimos o que a ANEPC, o IPMA e o ICNF publicam, normalizamos os dados e mostramo-los num mapa em direto — e numa API aberta, para quem quiser construir por cima.</p>
      <p>É uma plataforma independente, feita para ser simples de usar, rápida e fiável. Porque é nos piores dias que mais gente precisa dela.</p>
      <p class="links">
        <a href="https://emcurso.pt" target="_blank" rel="noopener"><strong>emcurso.pt</strong></a><span>·</span>
        <a href="https://api.emcurso.pt" target="_blank" rel="noopener">api.emcurso.pt</a><span>·</span>
        <a href="https://api.emcurso.pt/status" target="_blank" rel="noopener">Estado do serviço</a><span>·</span>
        <a href="https://api.emcurso.pt/contacto" target="_blank" rel="noopener">Contacto</a><span>·</span>
        <a href="https://x.com/emcursopt" target="_blank" rel="noopener">X</a>
      </p>
      <div class="gap"></div>
      {rest}
      <div class="gap"></div>
      <small>Os dados de origem pertencem às autoridades que os publicam. O EmCurso não é um serviço oficial — <strong>em caso de emergência, ligue 112.</strong></small>
    </article>
  </main>

  <p class="note">No GitHub o tema não se escolhe: cada visitante vê a versão que corresponde ao tema que tem. As animações correm dentro das próprias imagens, por isso funcionam lá exatamente como aqui.</p>
</div>

<script>
const IMGS = {json.dumps(imgs)};
const stage = document.getElementById("stage");
const buttons = [...document.querySelectorAll(".seg button")];
let round = 0;

function paint(mode) {{
  stage.dataset.mode = mode;
  buttons.forEach(b => b.setAttribute("aria-pressed", String(b.dataset.mode === mode)));
  // A new URL per paint, so each image starts its animations from the top.
  round += 1;
  document.querySelectorAll("img.card").forEach(img => {{
    img.src = IMGS[img.dataset.card + "-" + mode] + "#r" + round;
  }});
}}

function pageMode() {{
  const set = document.documentElement.dataset.theme;
  if (set === "dark" || set === "light") return set;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}}

buttons.forEach(b => b.addEventListener("click", () => paint(b.dataset.mode)));
document.getElementById("replay").addEventListener("click", () => paint(stage.dataset.mode));
paint(pageMode());
</script>
"""

out = os.path.join(PREVIEW, "preview.html")
open(out, "w", encoding="utf-8").write(html)
print("escrito", out, f"{len(html.encode('utf-8')) / 1024:.0f} KB")
