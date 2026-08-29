"""Omarchy theme -> UI palette.

The chrome (surface, ink, borders, accent) is read live from
/usr/share/omarchy/themes/<name>/colors.toml, so the bench wears whatever theme the
desktop is wearing.

CHART SERIES COLOURS ARE NOT THEME-DERIVED, deliberately. A theme's colors.toml is a
terminal palette: its red/green/blue are chosen to be legible as text on that
background, not to be distinguishable from each other as adjacent marks. Several of
the shipped themes have series pairs that collapse under colour-vision deficiency.
The categorical slots below are a fixed set validated with the dataviz palette
checker against the extreme surfaces on this machine -- #000000 (vantablack) and
#ffffff (white) -- passing the lightness band, chroma floor, CVD separation and
normal-vision floor in both modes.
"""
import os
import tomllib

THEME_DIR = os.environ.get("SB_THEMES", "/themes")
DEFAULT_THEME = os.environ.get("SB_THEME", "gruvbox")

# Validated categorical slots (dataviz reference instance). Series identity only.
SERIES_DARK = ["#3987e5", "#d95926", "#199e70", "#c98500"]
SERIES_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
# Status is reserved: verdicts, never series identity.
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}

FALLBACK = {
    "mode": "dark", "background": "#282828", "foreground": "#d4be98",
    "accent": "#7daea3", "muted": "#665c54", "selection": "#504945",
    "dark_background": "#1e1e1e", "lighter_background": "#3c3836",
    "red": "#ea6962", "green": "#a9b665", "yellow": "#d8a657", "blue": "#7daea3",
}


def list_themes():
    if not os.path.isdir(THEME_DIR):
        return [DEFAULT_THEME]
    out = [d for d in sorted(os.listdir(THEME_DIR))
           if os.path.exists(os.path.join(THEME_DIR, d, "colors.toml"))]
    return out or [DEFAULT_THEME]


def load(name=None):
    name = name or DEFAULT_THEME
    path = os.path.join(THEME_DIR, name, "colors.toml")
    colors = dict(FALLBACK)
    if os.path.exists(path):
        try:
            with open(path, "rb") as fh:
                colors.update({k: v for k, v in tomllib.load(fh).items() if isinstance(v, str)})
        except (OSError, tomllib.TOMLDecodeError):
            pass                                    # a malformed theme falls back, never 500s
    colors["name"] = name
    dark = colors.get("mode", "dark") != "light"
    colors["series"] = SERIES_DARK if dark else SERIES_LIGHT
    colors["is_dark"] = dark
    return colors


def css(colors):
    """The theme as custom properties. Everything else in the stylesheet reads these."""
    fg, bg = colors["foreground"], colors["background"]
    panel = colors.get("dark_background" if colors["is_dark"] else "lighter_background", bg)
    # `selection` is the most legible edge in practice: `lighter_background` sits only a
    # step off the panel on most dark themes and the chunky borders vanish into it.
    edge = colors.get("selection") or colors.get("muted") or fg
    series = "".join(f"  --series-{i + 1}: {c};\n" for i, c in enumerate(colors["series"]))
    status = "".join(f"  --status-{k}: {v};\n" for k, v in STATUS.items())
    return (
        ":root{\n"
        f"  --bg: {bg};\n"
        f"  --panel: {panel};\n"
        f"  --edge: {edge};\n"
        f"  --ink: {fg};\n"
        f"  --ink-dim: {colors.get('muted', fg)};\n"
        f"  --accent: {colors.get('accent', fg)};\n"
        f"  --sel: {colors.get('selection', panel)};\n"
        f"{series}{status}"
        "}\n"
    )
