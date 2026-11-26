"""Native offline control factories. All caller-supplied strings are plain text."""
from html import escape
import re
from .motion import motif_svg


_ID = re.compile(r"[a-z][a-z0-9-]{0,47}")


def _text(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 256:
        raise ValueError("Expected 1 to 256 characters of plain text")
    return escape(value, quote=True)


def effect_label(label, *, motif="shards"):
    """Decorate escaped text with a non-interactive, aria-hidden vector motif."""
    return '<span class="effect">' + _text(label) + motif_svg(motif) + '</span>'


class Controls:
    """One registry per page, preventing duplicate IDs and radio group collisions."""

    def __init__(self):
        self._ids = {"motion-off"}

    def _reserve(self, *names):
        if (any(not isinstance(name, str) or not _ID.fullmatch(name)
                or name in self._ids for name in names) or len(names) != len(set(names))):
            raise ValueError("Invalid or duplicate control ID")
        self._ids.update(names)

    def toggle(self, id, label, *, checked=False):
        if type(checked) is not bool:
            raise ValueError("Checked state must be boolean")
        label = effect_label(label, motif="ring")
        self._reserve(id)
        return (f'<label class="field switch-field" for="{id}"><input type="checkbox" role="switch" id="{id}"'
                + (" checked" if checked else "") + f'><span class="switch-track" aria-hidden="true"></span>'
                + f'{label}</label>')

    def radio(self, id, label, choices, *, selected=None, style="radio"):
        if not isinstance(style, str) or style not in {"radio", "segmented", "rating"}:
            raise ValueError("Unknown radio presentation")
        label = _text(label)
        if not isinstance(choices, (list, tuple)) or not 2 <= len(choices) <= 8:
            raise ValueError("Radio groups require 2 to 8 labels")
        motif = {"radio": "ring", "segmented": "slash", "rating": "spark"}[style]
        labels = [effect_label(choice, motif=motif) for choice in choices]
        if selected is not None and (type(selected) is not int or not 0 <= selected < len(labels)):
            raise ValueError("Invalid selected index")
        ids = tuple(f"{id}-{i}" for i in range(len(labels)))
        self._reserve(id, *ids)
        options = []
        for i, choice in enumerate(labels):
            checked = " checked" if selected == i else ""
            options.append(f'<label class="field" for="{ids[i]}"><input id="{ids[i]}" type="radio"'
                           f' name="{id}" value="{i}"{checked}>{choice}</label>')
        return f'<fieldset class="choice-{style}"><legend>{label}</legend><div class="choices">' + "".join(options) + "</div></fieldset>"

    def slider(self, id, label, *, value=40, maximum=100):
        if type(maximum) is not int or not 1 <= maximum <= 1000 or type(value) is not int or not 0 <= value <= maximum:
            raise ValueError("Invalid range")
        label = _text(label)
        self._reserve(id)
        return f'<label class="field-column" for="{id}">{label}<input id="{id}" type="range" min="0" max="{maximum}" value="{value}"></label>'

    def text(self, id, label, *, limit=80):
        if type(limit) is not int or not 1 <= limit <= 256:
            raise ValueError("Invalid input limit")
        label = _text(label)
        self._reserve(id)
        return f'<label class="field-column" for="{id}">{label}<input id="{id}" type="text" maxlength="{limit}" autocomplete="off"></label>'

    def select(self, id, label, choices):
        if not isinstance(choices, (list, tuple)) or not 2 <= len(choices) <= 8:
            raise ValueError("Select requires 2 to 8 labels")
        label = _text(label)
        options = "".join(f'<option value="{i}">{_text(choice)}</option>' for i, choice in enumerate(choices))
        self._reserve(id)
        return f'<label class="field-column" for="{id}">{label}<select id="{id}">{options}</select></label>'

    def progress(self, id, label, *, value=60):
        if type(value) is not int or not 0 <= value <= 100:
            raise ValueError("Invalid progress")
        label = _text(label)
        self._reserve(id)
        return f'<label class="field-column" for="{id}">{label} · {value}%<progress id="{id}" value="{value}" max="100">{value}%</progress></label>'

    def disclosure(self, id, label, detail):
        label, detail = effect_label(label, motif="slash"), _text(detail)
        self._reserve(id)
        return f'<details id="{id}"><summary>{label}</summary><p class="content muted">{detail}</p></details>'

    def notice(self, id, label, detail):
        """A user-triggered disclosure, not a fabricated live notification."""
        label, detail = effect_label(label, motif="cloud"), _text(detail)
        self._reserve(id)
        return f'<details class="notice" id="{id}"><summary><span class="action">{label}</span></summary><p class="content muted">{detail}</p></details>'
