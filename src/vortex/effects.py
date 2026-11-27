"""Bounded, frame-aligned visual effects for the local FFmpeg renderer."""
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

from .media import _decimal


@dataclass(frozen=True, slots=True)
class Effect:
    kind: str
    start_frame: int
    end_frame_exclusive: int
    strength: Decimal


def prepare_effects(effects, fps: int, total_frames: int) -> tuple[Effect, ...]:
    """Convert explicit output-time intervals in seconds to the render frame grid."""
    if effects is None:
        return ()
    raw = tuple(effects)
    if len(raw) > 32:
        raise ValueError("At most 32 effects per render")
    result = []
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) != 4:
            raise ValueError("Effect requires KIND START END STRENGTH")
        kind, start, end, strength = item
        if kind not in ("flash", "shake", "blur"):
            raise ValueError("Unknown visual effect")
        first = round(Fraction(_decimal(start)) * fps)
        last = round(Fraction(_decimal(end)) * fps)
        amount = _decimal(strength)
        if not 0 <= first < last <= total_frames or not 3 <= last - first <= 2 * fps:
            raise ValueError("Effect must span 3 frames to 2 seconds inside the output")
        if not 0 < amount <= 1:
            raise ValueError("Effect strength must be greater than zero and at most one")
        result.append(Effect(kind, first, last, amount))
    result.sort(key=lambda effect: (effect.start_frame, effect.kind))
    previous = {}
    for effect in result:
        last = previous.get(effect.kind)
        if last is not None and effect.start_frame < last.end_frame_exclusive:
            raise ValueError("Effects of the same kind cannot overlap")
        if (effect.kind == "flash" and last is not None and
                3 * (effect.start_frame - last.start_frame) < fps):
            raise ValueError("Space flash starts at least one third of a second apart")
        previous[effect.kind] = effect
    return tuple(result)


def effect_filters(effects: tuple[Effect, ...], fps: int) -> list[str]:
    """Generate numeric-only expressions; never accept arbitrary filter strings."""
    filters = []
    for effect in effects:
        first, last = effect.start_frame, effect.end_frame_exclusive - 1
        span = last - first
        amount = effect.strength
        inside = f"between(n,{first},{last})"
        pulse = f"(1-abs(2*(n-{first})/{span}-1))"
        if effect.kind == "flash":
            amplitude = amount * Decimal("0.45")
            filters.append(f"eq=brightness='if({inside},{amplitude:f}*{pulse},0)':eval=frame")
        elif effect.kind == "shake":
            amplitude = amount * Decimal("0.03")
            # Small rotational shake with a zero-amplitude start and end.
            wave = f"sin(2*PI*8*(n-{first})/{fps})"
            filters.append(f"rotate=angle='if({inside},{amplitude:f}*{pulse}*{wave},0)':"
                           "ow=iw:oh=ih:fillcolor=black")
        else:
            sigma = amount * 4
            filters.append(f"gblur=sigma={sigma:f}:steps=2:enable='{inside}'")
    return filters
