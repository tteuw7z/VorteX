"""Offline native-control UI candidates; no scripts, service or permission changes."""
import base64
from hashlib import sha256
from html import escape
from pathlib import Path

from .conversation import Conversation
from .design import audit as audit_design
from .discipline import prepare_task
from .motion import PRESETS, stylesheet
from .private_io import private_open
from .security import audit as audit_security
from .ui_components import Controls

COLORS = {
    "background": "#0d0b14", "surface": "#191426", "raised": "#241b36",
    "ink": "#f8f4ff", "muted": "#c8b9e2", "accent": "#c6a7ff",
    "line": "#8f6dd0", "button": "#30204c", "warning": "#ffdda0",
}
_CSS = """
*{box-sizing:border-box}
:root{color-scheme:dark;--bg:#0d0b14;--surface:#191426;--raised:#241b36;--ink:#f8f4ff;--muted:#c8b9e2;--accent:#c6a7ff;--line:#8f6dd0;--button:#30204c;--warning:#ffdda0}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,sans-serif}
main{width:min(100%,72rem);margin:auto;padding:clamp(16px,4vw,48px)}
a{color:var(--accent);text-underline-offset:.2em}
h1,h2,h3,p{margin:0}h1{font-size:clamp(2.4rem,7vw,4.7rem);line-height:1;letter-spacing:-.06em}h2{font-size:1.2rem}h3{font-size:1rem}
p{overflow-wrap:anywhere}.muted{color:var(--muted)}
.hero{display:grid;grid-template-columns:1fr auto;align-items:start;gap:12px;padding:24px 0}
.eyebrow{font-size:.77rem;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);font-weight:700}
.hero p{margin-top:12px;max-width:48rem}
.mark{width:72px;height:72px;color:var(--accent)}
.status{display:flex;align-items:center;gap:10px;padding:12px 16px;border:1px solid var(--line);border-radius:16px;background:var(--surface);color:var(--warning);margin-bottom:20px}
.status-dot{width:9px;height:9px;flex:none;border-radius:50%;background:var(--warning)}
.layout{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.panel{min-width:0;background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:16px;overflow-wrap:anywhere}
.panel[open]{grid-column:1/-1}
summary{cursor:pointer;min-height:48px;display:flex;align-items:center;gap:12px;list-style:none;padding:4px;position:relative}
summary::-webkit-details-marker{display:none}
summary:active,.action:active{transform:scale(.97,.92)}
summary::after{content:"+";margin-left:auto;font-size:1.5rem;color:var(--accent)}
details[open]>summary::after{content:"−"}
.number{font-size:.78rem;color:var(--accent);font-variant-numeric:tabular-nums;border:1px solid var(--line);border-radius:10px;padding:6px 9px}
.panel ul{display:grid;gap:8px;grid-template-columns:repeat(auto-fit,minmax(min(100%,15rem),1fr));padding:12px 0 0;margin:0;list-style:none}
.panel li{padding:12px;border:1px solid var(--line);border-radius:12px;background:var(--raised);min-width:0}
.panel li span{display:block;color:var(--muted);font-size:.875rem}
.panel li strong{font-weight:650}
.panel details p{margin-top:10px}
.motion-option{display:flex;align-items:center;gap:12px;min-height:48px;margin:12px 0;color:var(--muted)}
input,button,summary,a{accent-color:var(--accent)}
:focus-visible{outline:3px solid var(--accent);outline-offset:3px}
input[type=checkbox],input[type=radio]{width:22px;height:22px;flex:none}
input[type=range]{width:100%;min-height:44px}
input[type=text],select{width:100%;min-height:48px;background:var(--raised);border:1px solid var(--line);border-radius:12px;color:var(--ink);padding:10px;font:inherit}
.action{display:inline-flex;align-items:center;justify-content:center;min-height:48px;border:1px solid var(--line);border-radius:12px;background:var(--button);color:var(--ink);padding:10px 16px;font:inherit;text-decoration:none;cursor:pointer}
.field{display:flex;align-items:center;gap:10px;min-height:48px;position:relative}
.field-column{display:grid;gap:10px}.field-column fieldset{margin:0}
fieldset{min-width:0;border:1px solid var(--line);border-radius:12px;padding:8px 12px}
legend{color:var(--muted)}
progress{width:100%;height:18px;accent-color:var(--accent)}
.switch-field input{position:absolute;opacity:0;width:52px;height:40px;margin:0;cursor:pointer}
.switch-track{width:50px;height:30px;border:2px solid var(--line);border-radius:24px;flex:none;background:var(--raised);position:relative;pointer-events:none}
.switch-track::after{content:"";position:absolute;left:4px;top:4px;width:18px;height:18px;border-radius:50%;background:var(--accent)}
.switch-field input:checked+.switch-track{background:var(--button)}
.switch-field input:checked+.switch-track::after{left:24px;animation:vx-pop 350ms linear both}
.switch-field input:focus-visible+.switch-track{outline:3px solid var(--accent);outline-offset:3px}
.choice-segmented .choices,.choice-rating .choices{display:flex;flex-wrap:wrap;gap:6px}
.choice-segmented .field,.choice-rating .field{border:1px solid var(--line);border-radius:12px;padding:4px 8px;min-height:44px}
.choice-segmented .field:has(input:checked),.choice-rating .field:has(input:checked){background:var(--button)}
.choice-rating .field{min-width:52px;justify-content:center}
.notice summary::after{content:none}.notice .content{border-left:3px solid var(--accent);padding:10px 12px}
.gallery-card h2{margin-bottom:10px;color:var(--accent);font-size:.85rem;letter-spacing:.08em;text-transform:uppercase}
.gallery-card p{margin-top:8px}
@media(forced-colors:active){.switch-field input{position:static;opacity:1;width:22px;height:22px}.switch-track{display:none}}
footer{margin-top:28px;padding-top:16px;border-top:1px solid var(--line);color:var(--muted);font-size:.85rem}
.effect{display:inline-block;position:relative;min-width:0}
.effect::before,.effect::after{pointer-events:none;position:absolute;content:"";inset:-8px;border:2px solid var(--accent);border-radius:14px;transform:scale(0);visibility:hidden}
.effect::after{inset:-12px;border-style:dashed;border-color:var(--line);border-radius:3px 20px 3px 20px}
details[open]>summary .effect{animation:vx-impact 420ms linear both}
details[open]>summary .effect::before,.field:has(input:checked) .effect::before{animation:vx-ring 420ms linear both}
details[open]>summary .effect::after,.field:has(input:checked) .effect::after{animation:vx-shards 420ms linear both}
.field:has(input:checked) .effect{animation:vx-pop 350ms linear both}
details[open] .content{animation:vx-slide 460ms linear both}
.action:focus-visible{animation:vx-spark 300ms linear both}
@keyframes vx-ring{0%{visibility:visible;transform:scale(.75)}55%{transform:scale(1.15)}100%{visibility:hidden;transform:scale(1.25);border-width:0}}
@keyframes vx-shards{0%{visibility:visible;transform:rotate(-8deg) scale(.8)}60%{transform:rotate(5deg) scale(1.22)}100%{visibility:hidden;transform:rotate(8deg) scale(1.35);border-width:0}}
body:has(#motion-off:checked) *,body:has(#motion-off:checked) *::before,body:has(#motion-off:checked) *::after,.still *,.still *::before,.still *::after{animation:none!important;transition:none!important;transform:none!important}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important;transform:none!important}}
@media(max-width:600px){.layout{grid-template-columns:minmax(0,1fr)}.hero{grid-template-columns:1fr auto}.mark{width:52px;height:52px}}
@media(forced-colors:active){.panel,.status,.number,.action{border:1px solid ButtonText}}
"""
_MARK = """<svg class="mark" viewBox="0 0 80 80" aria-hidden="true" focusable="false"><path fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" d="M40 5 72 22 72 58 40 75 8 58 8 22Z M22 23 40 60 58 23 M30 23 40 43 50 23"/><circle cx="40" cy="12" r="2" fill="currentColor"/></svg>"""


def _language(locale):
    if not isinstance(locale, str) or locale.lower() not in {"en", "en-us", "pt", "pt-br"}:
        raise ValueError("Supported locales: en and pt-BR")
    return "pt-BR" if locale.lower().startswith("pt") else "en"


def _page(content, *, locale, title, still):
    if type(still) is not bool:
        raise ValueError("Still mode must be a boolean")
    css = _CSS + stylesheet()
    # Hash the exact inline stylesheet. All scripts and external loads are forbidden.
    css_hash = base64.b64encode(sha256(css.encode("utf-8")).digest()).decode("ascii")
    policy = "default-src 'none'; script-src 'none'; style-src 'sha256-" + css_hash + "'; base-uri 'none'; form-action 'none'; object-src 'none'"
    return ("<!doctype html><html lang=\"" + _language(locale) + "\"><head>"
            "<meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<meta http-equiv=\"Content-Security-Policy\" content=\"" + policy + "\">"
            "<meta name=\"referrer\" content=\"no-referrer\"><title>" + escape(title) + "</title><style>" +
            css + "</style></head><body" + (' class="still"' if still else "") +
            "><main>" + content + "</main></body></html>")


def _hero(title, subtitle, *, pt):
    status = "Visualização local · entrega não autorizada" if pt else "Local preview · delivery not authorized"
    motion = "Desativar animações" if pt else "Disable animations"
    return ('<header class="hero"><div><p class="eyebrow">VorteX / Motion UI</p><h1>' +
            escape(title) + '</h1><p class="muted">' + escape(subtitle) + '</p></div>' + _MARK +
            '</header><p class="status"><span class="status-dot" aria-hidden="true"></span>' +
            status + '</p><label class="motion-option"><input id="motion-off" type="checkbox">' +
            motion + '</label>')


def _rows(rows, empty):
    if not rows:
        return '<p class="muted">' + escape(empty) + '</p>'
    items = []
    for row in rows:
        label = escape(row["label"])
        detail = "".join("<span>" + escape(value) + "</span>" for value in
                         (row.get("status"), row.get("detail"), ", ".join(row.get("agents", ()))) if value)
        items.append("<li><strong>" + label + "</strong>" + detail + "</li>")
    return "<ul>" + "".join(items) + "</ul>"


def render_menu(*, locale="pt-BR", session=None, still=False):
    """Render a fresh read-only view without modifying the supplied host session."""
    lang = _language(locale)
    pt = lang == "pt-BR"
    if session is not None and not isinstance(session, Conversation):
        raise TypeError("Expected Conversation instance")
    view = Conversation(locale=lang, enabled=session.enabled if session else None,
                        execution_capabilities=session.execution_capabilities if session else frozenset(),
                        agent_limit=session.agent_limit if session else 3, interactive=True)
    view.handle("Vortex")
    menu = view.handle("menu")
    panels = []
    for index, item in enumerate(menu["navigation"], 1):
        section = view.handle(item["id"])
        panels.append('<details class="panel" id="section-' + escape(item["id"]) +
                      '"><summary><span class="number" aria-hidden="true">' + f"{index:02d}" +
                      '</span><span class="effect"><strong>' + escape(item["label"]) +
                      '</strong></span></summary><div class="content">' +
                      _rows(section["entries"], "Nenhuma ferramenta vinculada." if pt else "No bound tools.") +
                      '</div></details>')
    title = "Menu VorteX" if pt else "VorteX menu"
    subtitle = ("Explore agentes, funções e segurança. Nenhuma operação é executada aqui." if pt else
                "Explore agents, capabilities and security. No operation runs here.")
    footer = ("Interface de consulta. O host continua responsável por executar e autorizar." if pt else
              "Read-only interface. The host remains responsible for execution and authorization.")
    return _page(_hero(title, subtitle, pt=pt) + '<section class="layout" aria-label="' +
                 ("Seções" if pt else "Sections") + '">' + "".join(panels) + '</section><footer>' +
                 footer + '</footer>', locale=lang, title=title, still=still)


def render_gallery(*, locale="pt-BR", still=False):
    """Native examples, no fake submission, no input persistence, no network."""
    lang = _language(locale)
    pt = lang == "pt-BR"
    title = "Laboratório Motion" if pt else "Motion lab"
    subtitle = ("Controles nativos, efeitos decorativos e movimento reduzido." if pt else
                "Native controls, decorative effects and reduced motion.")
    labels = (("Alternar", "Escolher", "Intensidade", "Texto de teste", "Progresso de exemplo", "Detalhes", "Abrir / fechar")
              if pt else ("Toggle", "Choose", "Intensity", "Test text", "Example progress", "Details", "Open / close"))
    toggle, choose, intensity, text, progress, details, open_close = labels
    factory = Controls()
    controls = (
        ("Switch", factory.toggle("demo-switch", toggle)),
        ("Radio", factory.radio("choice", choose, ("A", "B"))),
        ("Slider", factory.slider("demo-range", intensity)),
        ("Input", factory.text("demo-text", text)),
        ("Progress", factory.progress("demo-progress", progress)),
        ("Disclosure", factory.disclosure("demo-details", open_close, details)),
        ("Select", factory.select("demo-select", "Tema" if pt else "Theme", ("Violet", "Graphite"))),
        ("Segmented", factory.radio("demo-segment", "Vista" if pt else "View",
                                    ("Menu", "Lab", "Info"), selected=0, style="segmented")),
        ("Rating", factory.radio("demo-rating", "Avaliação" if pt else "Rating",
                                 ("1 ★", "2 ★", "3 ★", "4 ★", "5 ★"), style="rating")),
        ("Notice", factory.notice("demo-notice", "Ver aviso" if pt else "Show notice",
                                  "Ação local, sem execução externa." if pt else "Local interaction, no external execution.")),
    )
    content = '<section class="layout">' + "".join(
        '<div class="panel gallery-card"><h2>' + name + '</h2>' + control + '</div>'
        for name, control in controls) + '</section>'
    return _page(_hero(title, subtitle, pt=pt) + content + '<footer>VorteX · Motion UI</footer>',
                 locale=lang, title=title, still=still)


def contrast_report():
    return audit_design({"name": "VorteX Motion", "colors": COLORS,
                         "contrast_pairs": [{"foreground": fg, "background": bg}
                                            for fg in ("ink", "muted", "accent", "warning")
                                            for bg in ("background", "surface", "raised", "button")]})


def write_preview(output: Path, *, mode="menu", locale="pt-BR", still=False, session=None):
    """Create one private candidate in a new directory; never publish or overwrite."""
    if mode not in {"menu", "gallery"}:
        raise ValueError("Unknown preview mode")
    economy = prepare_task("design UI motion accessibility")["economy"]
    page = (render_menu(locale=locale, session=session, still=still) if mode == "menu"
            else render_gallery(locale=locale, still=still))
    contrast = contrast_report()
    if contrast["status"] != "PASS":
        raise ValueError("Declared text contrast failed")
    output = Path(output).absolute()
    output.mkdir(mode=0o700)
    path = output / "index.html"
    with private_open(path) as stream:
        stream.write(page.encode("utf-8"))
    report = audit_security(output, "website")
    return {"status": "BLOCKED" if report["findings"] else "REVIEW_REQUIRED",
            "output": str(path), "mode": mode, "locale": _language(locale),
            "bytes": len(page.encode("utf-8")), "economy": economy,
            "motion_presets": list(PRESETS), "contrast": contrast, "security": report,
            "delivery_authorized": False, "scope": "offline preview only; independent gate required"}
