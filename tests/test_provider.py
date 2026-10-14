import json

import httpx
import pytest

from backend.providers.nebius import InvestigationAction, NebiusProvider, ProviderError


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

