"""Reversible reduction of caller-designated observations."""
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json


@dataclass(frozen=True, slots=True)
class ContextView:
    checkpoint: dict
    observations: dict
    omitted: dict[str, str]
    originals: dict[str, str] = field(repr=False)

    def summary(self) -> dict:
        payload = {"checkpoint": self.checkpoint, "observations": self.observations,
                   "omitted": self.omitted}
        size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        return {**deepcopy(payload), "estimated_tokens": (size + 3) // 4,
                "estimate_method": "ceil(UTF-8 JSON bytes / 4)"}

    def restore(self) -> dict:
        observations = deepcopy(self.observations)
        for name, digest in self.omitted.items():
            observations[name] = self.originals[digest]
        return {"checkpoint": deepcopy(self.checkpoint), "observations": observations}


class ContextEngine:
    def __init__(self, *, threshold: int = 4096):
        if type(threshold) is not int or threshold < 1:
            raise ValueError("Context threshold must be a positive integer")
        self.threshold = threshold

    def compact(self, checkpoint: dict, observations: dict) -> ContextView:
        if not isinstance(checkpoint, dict) or not isinstance(observations, dict):
            raise ValueError("Checkpoint and observations must be objects")
        for item in (checkpoint, observations):
            if json.loads(json.dumps(item, allow_nan=False)) != item:
                raise ValueError("Context must be JSON data")
        kept, omitted, originals = {}, {}, {}
        for name, value in observations.items():
            if isinstance(value, str) and len(data := value.encode("utf-8")) > self.threshold:
                digest = hashlib.sha256(data).hexdigest()
                originals.setdefault(digest, value)
                omitted[name] = digest
            else:
                kept[name] = deepcopy(value)
        return ContextView(deepcopy(checkpoint), kept, omitted, originals)
