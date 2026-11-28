"""Minimal environment for trusted installed tooling; not an OS sandbox."""
import os

_BASE = frozenset(("PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "WINDIR", "COMSPEC",
                   "PATHEXT", "TMP", "TEMP", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE",
                   "JAVA_HOME", "TESSDATA_PREFIX", "FONTCONFIG_PATH"))
_RESERVED = frozenset(("VORTEX_DELIVERY_KEY_HEX", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                       "GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PAT"))


def tool_environment(*, extra=()):
    """Only copy explicitly named operational settings; never pass verifier/provider keys."""
    requested = set(extra)
    if {name.upper() for name in requested} & _RESERVED:
        raise ValueError("Reserved security credentials cannot be forwarded to tools")
    names = _BASE | requested
    # Windows environment names are case-insensitive.
    return {name: value for name, value in os.environ.items()
            if (name.upper() if os.name == "nt" else name) in names}
