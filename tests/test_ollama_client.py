from __future__ import annotations

import httpx

from backend.generation.ollama_client import OllamaChatClient


def test_ollama_chat_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        return httpx.Response(
            200,
            json={"message": {"content": '{"answer":"ok"}'}},
        )

    client = OllamaChatClient(
        base_url="http://ollama.test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    response = client.chat.completions.create(
        model="llama3.2",
        messages=[{"role": "user", "content": "Return JSON"}],
        response_format={"type": "json_object"},
    )

    assert response.choices[0].message.content == '{"answer":"ok"}'


def test_ollama_chat_requests_json_format() -> None:
    seen_payload: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen_payload.update(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"message": {"content": "{}"}})

    client = OllamaChatClient(
        base_url="http://ollama.test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    client.chat.completions.create(
        model="llama3.2",
        messages=[{"role": "user", "content": "Return JSON"}],
        response_format={"type": "json_object"},
    )

    assert seen_payload["format"] == "json"
    assert seen_payload["stream"] is False
