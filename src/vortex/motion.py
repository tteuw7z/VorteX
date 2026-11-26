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


def stylesheet():
    return "\n".join(preset.keyframes(name) for name, preset in PRESETS.items())
