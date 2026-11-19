"""Tests for Theme Token parity, config.toml synchronization, and WCAG contrast compliance.
Written in Phase P0 to enforce token integrity.
"""

import configparser
from pathlib import Path
import pytest
from app import THEMES


def parse_color(c, bg=(255, 255, 255)):
    """Parse hex or rgba color string into an (R, G, B) tuple alpha-composited over bg."""
    c = c.strip()
    if c.startswith("#"):
        c = c.lstrip("#")
        if len(c) == 3:
            c = "".join([x * 2 for x in c])
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    if c.startswith("rgba"):
        parts = c[c.find("(") + 1:c.find(")")].split(",")
        r, g, b = [int(p.strip()) for p in parts[:3]]
        a = float(parts[3].strip())
        br, bg_g, bb = bg
        return (round(r * a + br * (1 - a)), round(g * a + bg_g * (1 - a)), round(b * a + bb * (1 - a)))
    raise ValueError(f"Unsupported color format: {c}")


def rel_luminance(rgb):
    """Calculate WCAG 2.1 relative luminance for an (R, G, B) tuple."""
    def channel(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = [channel(v) for v in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg, bg_color, base_bg=(255, 255, 255)):
    """Compute WCAG contrast ratio with alpha compositing."""
    rgb_bg = parse_color(bg_color, base_bg)
    rgb_fg = parse_color(fg, rgb_bg)
    l1 = rel_luminance(rgb_fg)
    l2 = rel_luminance(rgb_bg)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def test_theme_keys_parity():
    """Verify light and dark themes have exact identical key sets."""
    light_keys = set(THEMES["light"].keys())
    dark_keys = set(THEMES["dark"].keys())
    assert light_keys == dark_keys, f"Missing in dark: {light_keys - dark_keys}, missing in light: {dark_keys - light_keys}"


def test_config_toml_matches_themes():
    """Verify shared keys in .streamlit/config.toml match THEMES in app.py."""
    config_path = Path(__file__).resolve().parent.parent / ".streamlit" / "config.toml"
    assert config_path.exists(), "config.toml not found"

    config = configparser.ConfigParser()
    config.read(config_path)

    assert "theme.light" in config, "Missing [theme.light] in config.toml"
    assert "theme.dark" in config, "Missing [theme.dark] in config.toml"

    # Light mappings
    cfg_l = config["theme.light"]
    th_l = THEMES["light"]
    assert cfg_l["primaryColor"].strip('"\'').lower() == th_l["primary"].lower()
    assert cfg_l["backgroundColor"].strip('"\'').lower() == th_l["bg"].lower()
    assert cfg_l["textColor"].strip('"\'').lower() == th_l["text"].lower()

    # Dark mappings
    cfg_d = config["theme.dark"]
    th_d = THEMES["dark"]
    assert cfg_d["primaryColor"].strip('"\'').lower() == th_d["primary"].lower()
    assert cfg_d["backgroundColor"].strip('"\'').lower() == th_d["bg"].lower()
    assert cfg_d["textColor"].strip('"\'').lower() == th_d["text"].lower()


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_theme_wcag_contrast_rules(mode):
    """Assert WCAG contrast rules for text, primary, buttons, borders, and status colors."""
    t = THEMES[mode]

    # 1. Text >= 4.5:1 on background, card, and sidebar
    for surface_key in ("bg", "card", "sidebar"):
        ratio = contrast_ratio(t["text"], t[surface_key])
        assert ratio >= 4.5, f"[{mode}] text on {surface_key} contrast {ratio:.2f} < 4.5"

    # 2. Primary button text: on_primary on primary >= 4.5:1
    on_primary_ratio = contrast_ratio(t["on_primary"], t["primary"])
    assert on_primary_ratio >= 4.5, f"[{mode}] on_primary on primary contrast {on_primary_ratio:.2f} < 4.5"

    # 3. Primary action on card/bg >= 4.5:1 (for high-contrast links and badges)
    primary_card_ratio = contrast_ratio(t["primary"], t["card"])
    assert primary_card_ratio >= 4.5, f"[{mode}] primary on card contrast {primary_card_ratio:.2f} < 4.5"

    # 4. Input border on card >= 3.0:1 (WCAG UI component boundary)
    border_ratio = contrast_ratio(t["input_border"], t["card"])
    assert border_ratio >= 3.0, f"[{mode}] input_border on card contrast {border_ratio:.2f} < 3.0"

    # 5. Semantic colors on card >= 4.5:1
    for sem in ("success", "warning", "danger"):
        sem_ratio = contrast_ratio(t[sem], t["card"])
        assert sem_ratio >= 4.5, f"[{mode}] semantic {sem} on card contrast {sem_ratio:.2f} < 4.5"


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_primary_button_css_rule(mode):
    """Verify inject_theme_css outputs targeted rules covering primary button labels with var(--on-primary)."""
    from app import inject_theme_css

    css = inject_theme_css(mode)
    assert css is not None, "inject_theme_css should return the generated CSS string"
    # Ensure primary button testids and kind are targeted
    assert 'button[data-testid="stBaseButton-primary"]' in css
    assert '[data-testid="stFormSubmitButton"]' in css
    assert "var(--on-primary)" in css

    # Ensure targeted label selector references var(--on-primary) !important
    assert "color: var(--on-primary) !important;" in css


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_color_mix_tints_contrast(mode):
    """Verify 12% color-mix tints over card keep text contrast >= 4.5:1 in both modes."""
    t = THEMES[mode]
    card_rgb = parse_color(t["card"])
    text_rgb = parse_color(t["text"])

    for sem_key in ("warning", "info", "success", "danger"):
        sem_rgb = parse_color(t[sem_key])
        # 12% semantic color + 88% card surface
        tint_rgb = tuple(round(0.12 * s + 0.88 * c) for s, c in zip(sem_rgb, card_rgb))
        l_text = rel_luminance(text_rgb)
        l_tint = rel_luminance(tint_rgb)
        ratio = (max(l_text, l_tint) + 0.05) / (min(l_text, l_tint) + 0.05)
        assert ratio >= 4.5, f"[{mode}] text on {sem_key} tint contrast {ratio:.2f} < 4.5"
