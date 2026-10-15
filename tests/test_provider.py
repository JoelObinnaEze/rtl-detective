import json

import httpx
import pytest

from backend.providers.nebius import (
    InvestigationAction,
    NebiusProvider,
    PatchAction,
    ProviderError,
    TransactionAction,
)


def test_discovers_only_available_nvidia_models() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "nvidia/example-nemotron", "name": "Nemotron", "owned_by": "system"},
                    {"id": "other/model", "name": "Other", "owned_by": "system"},
                ]
            },
        )

    provider = NebiusProvider(
        api_key="test-key",
        model_id="nvidia/example-nemotron",
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.tokenfactory.nebius.com/v1/"),
    )

    assert provider.discover_nvidia_models() == ["nvidia/example-nemotron"]
    provider.verify_model()


def test_rejects_configured_model_not_returned_by_account() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"data": []}))
    provider = NebiusProvider(
        api_key="test-key",
        model_id="invented/model",
        client=httpx.Client(transport=transport, base_url="https://api.tokenfactory.nebius.com/v1/"),
    )

    with pytest.raises(ProviderError, match="not an available NVIDIA"):
        provider.verify_model()


def test_investigation_response_is_schema_validated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "nvidia/example-nemotron"
        assert body["max_tokens"] == 512
        assert body["chat_template_kwargs"] == {"enable_thinking": False}
        assert body["response_format"] == {
            "type": "json_schema",
            "json_schema": {
                "name": "InvestigationAction",
                "schema": InvestigationAction.model_json_schema(),
                "strict": True,
            },
        }
        return httpx.Response(
            200,
            headers={"x-request-id": "request-1"},
            json={
                "id": "completion-1",
                "model": "nvidia/example-nemotron",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "hypothesis": "Count is overwritten when read and write are both accepted.",
                                    "evidence_cycles": [6],
                                    "transactions": [
                                        {"rst": True, "wr_en": False, "rd_en": False, "din": 0},
                                        {"rst": False, "wr_en": True, "rd_en": False, "din": 1},
                                    ],
                                }
                            )
                        }
                    }
                ],
            },
        )

    provider = NebiusProvider(
        api_key="test-key",
        model_id="nvidia/example-nemotron",
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.tokenfactory.nebius.com/v1/"),
        max_tokens=512,
    )

    reply = provider.investigate("bounded evidence")

    assert isinstance(reply.value, InvestigationAction)
    assert reply.request_id == "request-1"
    assert reply.usage["total_tokens"] == 15


def test_malformed_model_output_is_a_provider_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})
    )
    provider = NebiusProvider(
        api_key="test-key",
        model_id="nvidia/example-nemotron",
        client=httpx.Client(transport=transport, base_url="https://api.tokenfactory.nebius.com/v1/"),
        retries=0,
    )

    with pytest.raises(ProviderError, match="structured response"):
        provider.investigate("bounded evidence")


def test_investigation_transaction_can_describe_an_arbiter_request() -> None:
    action = TransactionAction(rst=False, request=0b101)

    assert action.request == 0b101


def test_patch_prompt_requires_canonical_dut_source_lines() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        assert "complete corrected dut.sv as source_lines" in system
        assert "exactly one SystemVerilog line" in system
        assert "module header, parameter defaults, and ports byte-for-byte" in system
        return httpx.Response(
            200,
            json={
                "model": "nvidia/example-nemotron",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "diagnosis": "The count assignments conflict.",
                                    "source_lines": ["module fifo;", "endmodule"],
                                }
                            )
                        }
                    }
                ],
            },
        )

    provider = NebiusProvider(
        api_key="test-key",
        model_id="nvidia/example-nemotron",
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.tokenfactory.nebius.com/v1/"),
        retries=0,
    )

    patch = provider.propose_patch("bounded evidence").value

    assert isinstance(patch, PatchAction)
    assert patch.source_lines == ["module fifo;", "endmodule"]


def test_from_env_applies_the_live_request_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")
    monkeypatch.setenv("NEBIUS_MODEL_ID", "nvidia/example-nemotron")
    monkeypatch.setenv("NEBIUS_MAX_RETRIES", "0")
    monkeypatch.setenv("NEBIUS_MAX_OUTPUT_TOKENS", "768")

    provider = NebiusProvider.from_env()
    try:
        assert provider.retries == 0
        assert provider.max_tokens == 768
    finally:
        provider.client.close()


def test_from_env_rejects_an_invalid_live_request_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")
    monkeypatch.setenv("NEBIUS_MODEL_ID", "nvidia/example-nemotron")
    monkeypatch.setenv("NEBIUS_MAX_OUTPUT_TOKENS", "not-a-number")

    with pytest.raises(ProviderError, match="integer"):
        NebiusProvider.from_env()


@pytest.mark.parametrize(
    ("name", "value"),
    [("NEBIUS_MAX_RETRIES", "3"), ("NEBIUS_MAX_OUTPUT_TOKENS", "128")],
)
def test_from_env_rejects_an_out_of_range_live_request_budget(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")
    monkeypatch.setenv("NEBIUS_MODEL_ID", "nvidia/example-nemotron")
    monkeypatch.setenv(name, value)

    with pytest.raises(ProviderError, match="between"):
        NebiusProvider.from_env()

