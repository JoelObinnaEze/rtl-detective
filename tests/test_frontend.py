from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_frontend_has_accessible_primary_flow_and_no_inline_scripts() -> None:
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")

    assert '<label for="contract">' in html
    assert '<label for="example">' in html
    assert '<label for="data-width">' in html
    assert 'aria-live="polite"' in html
    assert "Selected FIFO contract" in html
    assert "No formal-correctness claim" in html
    assert "<script>" not in html


def test_frontend_selects_a_contract_pack_and_only_submits_relevant_parameters() -> None:
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    script = (ROOT / "frontend/app.js").read_text(encoding="utf-8")

    assert '<option value="arbiter">Round-robin arbiter</option>' in html
    assert 'id="arbiter-parameters"' in html
    assert '<label for="requesters">' in html
    assert 'href="#workspace"' in html
    assert "item.contractId === contract.value" in script
    assert "contractId: contract.value" in script
    assert "requesters: Number(requesters.value)" in script
    assert "dataWidth: Number(dataWidth.value)" in script


def test_frontend_does_not_render_server_content_as_html() -> None:
    script = (ROOT / "frontend/app.js").read_text(encoding="utf-8")

    assert ".innerHTML" not in script
    assert ".textContent" in script


def test_frontend_explains_the_verification_pipeline_and_uses_precise_motion() -> None:
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    styles = (ROOT / "frontend/styles.css").read_text(encoding="utf-8")

    assert 'aria-label="Verification pipeline"' in html
    assert html.count('class="pipeline-step"') == 4
    assert 'class="button-label">Start verification</span>' in html
    assert '<link rel="icon" href="/favicon.svg" type="image/svg+xml">' in html
    assert (ROOT / "frontend/favicon.svg").is_file()
    assert "transition: all" not in styles
    assert "min-width: 320px" not in styles
    assert ":active:not(:focus-visible)" in styles
    assert "prefers-reduced-motion: reduce" in styles


def test_frontend_surfaces_the_proof_chain_and_runtime_provider() -> None:
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    script = (ROOT / "frontend/app.js").read_text(encoding="utf-8")

    assert "Nebius Token Factory × NVIDIA Nemotron" in html
    assert 'id="proof-panel"' in html
    assert 'id="proof-claim"' in html
    assert 'id="proof-gates"' in html
    assert "function renderProof(report)" in script
    assert "report?.claim" in script
    assert "locked_assets_unchanged" in script

