"""Design-token validation, text contrast checks, and a local preview."""

from html import escape
from pathlib import Path
import re
from .private_io import private_open


_TOKEN = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}")
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?")
_CONTRAST_REFERENCE = "https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html"


def _token_map(document: dict, key: str) -> dict:
    values = document.get(key, {})
    if not isinstance(values, dict) or any(
        not isinstance(name, str) or not _TOKEN.fullmatch(name) for name in values
    ):
        raise ValueError(f"{key} must be an object with named tokens")
    return values


def _color(value: str) -> str:
    if not isinstance(value, str) or not _HEX_COLOR.fullmatch(value):
        raise ValueError("Colors must be opaque #RGB or #RRGGBB values")
    if len(value) == 4:
        value = "#" + "".join(digit * 2 for digit in value[1:])
    return value.lower()


def _luminance(color: str) -> float:
    channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
              for channel in channels]
    red, green, blue = linear
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast_checks(pairs: list, colors: dict, typography: dict) -> list[dict]:
    checks = []
    seen = set()
    for pair in pairs:
        if not isinstance(pair, dict) or not {"foreground", "background"} <= pair.keys() or (
            pair.keys() - {"foreground", "background", "typography"}
        ):
            raise ValueError("Each contrast pair needs foreground and background token names")
        foreground, background, style = (pair.get(key) for key in
                                         ("foreground", "background", "typography"))
        if any(not isinstance(name, str) or name not in colors for name in (foreground, background)):
            raise ValueError("Contrast pair references an unknown color token")
        if style is not None and (not isinstance(style, str) or style not in typography):
            raise ValueError("Contrast pair references an unknown typography token")
        identity = foreground, background, style
        if identity in seen:
            raise ValueError("Duplicate contrast pair")
        seen.add(identity)
        size, weight = typography.get(style, (16.0, 400))
        # 18pt regular or 14pt bold, converted using 96 CSS px per inch.
        large_text = size >= 24 or (size >= 14 * 96 / 72 and weight >= 700)
        minimum = 3.0 if large_text else 4.5
        darker, brighter = sorted(_luminance(colors[name]) for name in (foreground, background))
        ratio = (brighter + 0.05) / (darker + 0.05)
        checks.append({"foreground": foreground, "background": background, "typography": style,
                       "size_px": size, "weight": weight, "ratio": ratio, "minimum": minimum,
                       "passes": ratio >= minimum})
    return checks


def audit(document: dict) -> dict:
    """Validate the token schema and evaluate declared WCAG 2.2 AA text pairs."""
    allowed = {"name", "colors", "spacing", "typography", "contrast_pairs"}
    if not isinstance(document, dict) or document.keys() - allowed:
        raise ValueError("Design must be a token object")
    name = document.get("name", "Design tokens")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Design name must be text")
    colors = {token: _color(value) for token, value in _token_map(document, "colors").items()}
    if not colors:
        raise ValueError("Design must declare at least one color")
    spacing = _token_map(document, "spacing")
    for value in spacing.values():
        if type(value) not in (int, float) or not 0 <= value <= 512:
            raise ValueError("Spacing tokens must be pixel values between 0 and 512")
    typography = {}
    for token, value in _token_map(document, "typography").items():
        if not isinstance(value, dict) or value.keys() != {"size_px", "weight"}:
            raise ValueError("Typography tokens require size_px and weight")
        size, weight = value["size_px"], value["weight"]
        if type(size) not in (int, float) or not 1 <= size <= 256:
            raise ValueError("Typography size must be between 1 and 256 CSS px")
        if type(weight) is not int or not 100 <= weight <= 900:
            raise ValueError("Typography weight must be an integer between 100 and 900")
        typography[token] = size, weight
    pairs = document.get("contrast_pairs", [])
    if not isinstance(pairs, list):
        raise ValueError("contrast_pairs must be an array")
    checks = _contrast_checks(pairs, colors, typography)
    status = "UNVERIFIED"
    if checks:
        status = "PASS" if all(row["passes"] for row in checks) else "REVIEW_REQUIRED"
    return {"status": status, "name": name, "colors": colors, "spacing": spacing,
            "typography": {key: {"size_px": size, "weight": weight}
                           for key, (size, weight) in typography.items()},
            "contrast": checks, "scope": "declared text contrast pairs", "reference": _CONTRAST_REFERENCE}


def preview(document: dict, output: Path) -> dict:
    """Render the audited tokens as a self-contained HTML page."""
    result = audit(document)
    colors = result["colors"]
    title = escape(result["name"])
    swatches = "".join(
        f'<li><span class="swatch" style="background:{color}"></span>'
        f'<strong>{escape(name)}</strong> <code>{color}</code></li>'
        for name, color in colors.items()
    )
    samples = []
    for check in result["contrast"]:
        foreground, background = check["foreground"], check["background"]
        ratio = check["ratio"]
        label = "Pass" if check["passes"] else "Needs review"
        samples.append(
            f'<li><p class="sample" style="color:{colors[foreground]};'
            f'background:{colors[background]};font-size:{check["size_px"]}px;'
            f'font-weight:{check["weight"]}" aria-hidden="true">Sample text</p>'
            f'<strong>{escape(foreground)} / {escape(background)}</strong>'
            f'<p>{label}. {ratio:.2f}:1 · Minimum {check["minimum"]:g}:1</p></li>'
        )
    spacing = "".join(
        f'<li><span class="measure" style="width:{size}px" aria-hidden="true"></span>'
        f'<strong>{escape(name)}</strong> {size:g} px</li>'
        for name, size in result["spacing"].items()
    )
    styles = "".join(
        f'<li><p class="type-sample" style="font-size:{style["size_px"]}px;'
        f'font-weight:{style["weight"]}" aria-hidden="true">Aa</p>'
        f'<strong>{escape(name)}</strong> {style["size_px"]:g} px · {style["weight"]}</li>'
        for name, style in result["typography"].items()
    )
    sections = [
        f"<section><h2>{heading}</h2><ul>{items}</ul></section>"
        for heading, items in (("Colors", swatches), ("Contrast", "".join(samples)),
                               ("Spacing", spacing), ("Typography", styles))
        if items
    ]
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>{title}</title>
<style>
* {{ box-sizing:border-box }}
body {{ margin:0; background:#f6f4f8; color:#201829; font:16px/1.5 system-ui,sans-serif }}
main {{ max-width:68rem; margin:auto; padding:clamp(1rem,4vw,4rem) }}
h1 {{ margin:0 0 1.5rem; font-size:clamp(2rem,5vw,3.5rem); line-height:1.05;
      overflow-wrap:anywhere }}
h2 {{ margin:2rem 0 .8rem; font-size:1.35rem }}
ul {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(min(14rem,100%),1fr));
      gap:.8rem; list-style:none; padding:0; margin:0 }}
li {{ background:#fff; border:1px solid #d8d1df; border-radius:.8rem;
      overflow-wrap:anywhere; min-width:0; padding:.8rem }}
p {{ margin:.4rem 0 0 }}
.swatch,.measure {{ display:block; max-width:100%; margin:0 0 .75rem }}
.swatch {{ height:3.5rem; border:1px solid #a89caf; border-radius:.4rem }}
.measure {{ height:.5rem; background:#604181 }}
.sample {{ padding:.75rem; margin:0 0 .75rem; border-radius:.4rem }}
.type-sample {{ margin:0 0 .75rem }}
</style>
</head>
<body><main><h1>{title}</h1>{"".join(sections)}</main></body>
</html>
"""
    with private_open(output, text=True) as target:
        target.write(page)
    return {**result, "output": str(output)}
