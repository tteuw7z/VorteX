"""Original bounded UI motion recipes; Python generates the browser keyframes."""
from dataclasses import dataclass
from math import cos, exp, isfinite, sin, sqrt
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class Motion:
    duration_ms: int
    stiffness: float
    damping: float
    squash: float
    travel_px: float
    accent: str

    def __post_init__(self):
        if type(self.duration_ms) is not int or not 180 <= self.duration_ms <= 900:
            raise ValueError("Motion duration outside allowed bounds")
        values = (self.stiffness, self.damping, self.squash, self.travel_px)
        if any(type(n) not in (int, float) or not isfinite(n) for n in values):
            raise ValueError("Motion values must be finite numbers")
        if not (80 <= self.stiffness <= 700 and 8 <= self.damping <= 40
                and self.damping ** 2 < 4 * self.stiffness
                and 0 <= self.squash <= .18 and 0 <= self.travel_px <= 24):
            raise ValueError("Motion exceeds safe design bounds")
        if self.accent not in {"ring", "shards", "slash", "spark", "none"}:
            raise ValueError("Unknown motion accent")

    def frame(self, t):
        """Return transform values at normalized time, with exact settled endpoint."""
        if type(t) not in (int, float) or not isfinite(t) or not 0 <= t <= 1:
            raise ValueError("Frame time must be in [0, 1]")
        if t == 1:
            return 1.0, 1.0, 0.0
        seconds = t * self.duration_ms / 1000
        decay = self.damping / 2
        omega = sqrt(self.stiffness - decay ** 2)
        displacement = exp(-decay * seconds) * (
            cos(omega * seconds) + decay / omega * sin(omega * seconds))
        # Smoothly remove residual energy over the last quarter.
        displacement *= min(1.0, (1 - t) * 4)
        scale_y = max(.82, min(1.18, 1 - self.squash * displacement))
        return 1 / scale_y, scale_y, self.travel_px * displacement

    def keyframes(self, name):
        if name not in PRESETS or PRESETS[name] is not self:
            raise ValueError("Only registered CSS motion names are allowed")
        rows = []
        for index in range(25):
            x, y, travel = self.frame(index / 24)
            rows.append(f"{index * 100 / 24:.4f}%{{transform:translateY({travel:.3f}px) scale({x:.4f},{y:.4f})}}")
        return "@keyframes vx-" + name + "{" + "".join(rows) + "}"


PRESETS = MappingProxyType({
    "impact": Motion(420, 390, 19, .13, 0, "shards"),
    "slide": Motion(460, 270, 17, .05, 12, "slash"),
    "pop": Motion(350, 440, 21, .12, 0, "ring"),
    "settle": Motion(520, 230, 15, .035, 8, "none"),
    "spark": Motion(300, 520, 23, .08, 0, "spark"),
})


# Fixed, original vector motifs. Never interpolate caller-supplied path data.
_MOTIFS = MappingProxyType({
    "shards": '<path class="fx-fill" d="M38 31 44 12 49 29 66 18 58 37 78 39 61 48 69 67 49 56 41 75 35 56 15 64 25 46 7 39 27 35 19 18Z"/><path class="fx-accent" d="M73 9 79 4 77 17Z M8 68 3 77 17 74Z"/><path class="fx-line" d="M39 22 43 7 M58 59 70 72 M12 24 3 19"/>',
    "ring": '<circle class="fx-line" cx="40" cy="40" r="25"/><path class="fx-fill" d="M11 37 20 24 25 36 20 49Z M60 49 70 36 76 48 66 60Z"/><path class="fx-accent" d="M40 3 45 14 40 20 35 14Z M40 60 45 66 40 77 35 66Z"/>',
    "slash": '<path class="fx-fill" d="M9 53Q25 12 70 11Q43 24 31 49Q47 47 71 29Q54 64 9 70Z"/><path class="fx-line" d="M6 38 25 19 M58 65 74 52"/><path class="fx-accent" d="M65 6 76 3 72 13Z"/>',
    "spark": '<path class="fx-fill" d="M40 5 48 30 74 40 48 50 40 75 32 50 6 40 32 30Z"/><path class="fx-accent" d="M66 9 70 18 79 22 70 26 66 35 62 26 53 22 62 18Z"/>',
    "cloud": '<path class="fx-fill" d="M11 49Q2 36 17 28Q18 14 32 18Q44 6 57 21Q73 18 75 35Q83 48 69 55Q65 69 49 64Q34 75 24 61Q7 64 11 49Z"/><path class="fx-line" d="M25 29Q34 23 43 30 M48 48Q57 43 64 48"/>',
})


def motif_svg(name):
    if not isinstance(name, str) or name not in _MOTIFS:
        raise ValueError("Unknown motion motif")
    return ('<svg class="fx fx-' + name + '" viewBox="0 0 80 80" aria-hidden="true" focusable="false">' +
            _MOTIFS[name] + '</svg>')


def stylesheet():
    durations = ":root{" + "".join(f"--vx-{name}-ms:{preset.duration_ms}ms;"
                                   for name, preset in PRESETS.items()) + "}"
    return durations + "\n" + "\n".join(preset.keyframes(name) for name, preset in PRESETS.items())
