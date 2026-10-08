"""Every asset file must be credited (licence + URL) in CREDITS.md."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LICENCE_WORDS = ("CC0", "CC-BY", "CC BY", "OGA-BY", "GPL", "MIT")


def asset_files():
    return [p for p in (ROOT / "assets").rglob("*") if p.is_file() and not p.name.startswith(".")]


def test_every_asset_is_credited():
    credits = (ROOT / "CREDITS.md").read_text()
    missing = [str(p.relative_to(ROOT)) for p in asset_files() if str(p.relative_to(ROOT)) not in credits]
    assert not missing, f"add these to CREDITS.md with licence and URL: {missing}"


def test_each_credit_line_has_a_licence_and_url():
    credits = (ROOT / "CREDITS.md").read_text().splitlines()
    for p in asset_files():
        rel = str(p.relative_to(ROOT))
        line = next(line for line in credits if rel in line)
        assert any(w in line for w in LICENCE_WORDS), f"{rel}: no licence on its CREDITS line"
        assert "http" in line, f"{rel}: no source URL on its CREDITS line"
