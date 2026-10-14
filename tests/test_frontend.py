from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_frontend_has_accessible_primary_flow_and_no_inline_scripts() -> None:
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")

    assert '<label for="example">' in html
    assert '<label for="data-width">' in html
    assert 'aria-live="polite"' in html
    assert "Selected FIFO contract" in html
    assert "No formal-correctness claim" in html
    assert "<script>" not in html


def test_frontend_does_not_render_server_content_as_html() -> None:
    script = (ROOT / "frontend/app.js").read_text(encoding="utf-8")

    assert ".innerHTML" not in script
    assert ".textContent" in script

