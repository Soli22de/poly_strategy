import importlib.util
from pathlib import Path
from unittest.mock import patch


def load_experiment_module():
    root = Path(__file__).resolve().parents[1]
    path = root / "scripts" / "experiment_llm_complex_recognition.py"
    spec = importlib.util.spec_from_file_location("experiment_llm_complex_recognition", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_complex_recognition_builds_streaming_chat_payload():
    module = load_experiment_module()

    body = module.build_body("chat_stream", "test-model", "QUESTION:\nWill A happen?")

    assert body["model"] == "test-model"
    assert body["stream"] is True
    assert body["response_format"]["type"] == "json_object"
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][1]["role"] == "user"


def test_complex_recognition_routes_streaming_chat_calls():
    module = load_experiment_module()

    class Provider:
        base_url = "https://example.test/v1"
        api_key = "test-key"

    with patch.object(
        module.ENDPOINT,
        "request_stream",
        return_value=({"choices": [{"message": {"content": "{\"ok\": true}"}}]}, 1.25),
    ) as request_stream:
        text, usage, elapsed = module.call_model(
            Provider(),
            opener=object(),
            api_format="chat_stream",
            model="test-model",
            transcript="QUESTION:\nWill A happen?",
            timeout=12,
        )

    assert text == "{\"ok\": true}"
    assert usage == {}
    assert elapsed == 1.25
    request_stream.assert_called_once()
    body = request_stream.call_args.args[3]
    assert body["stream"] is True
