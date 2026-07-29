"""OpenAI-compatible backend tests — urllib is always monkeypatched; no live calls.

The ``openai_compat`` backend runs any model behind an OpenAI-shaped
``/chat/completions`` endpoint: OpenAI itself, xAI Grok, DeepSeek, Zhipu GLM,
Moonshot Kimi, OpenRouter, Together, or a local proxy. One backend, many
providers — the base URL and the API-key env var are configured, the cohort
just lists that provider's model ids with ``backend: openai_compat``.

These pin the request shape (endpoint, bearer auth, message roles, effort and
extra-body passthrough), the response parse, and fail-fast vs retry semantics.
"""

import io
import json
import urllib.error
import urllib.request

import pytest

import deseretbench.runner as R


def _oai_json(**over):
    d = {
        "id": "chatcmpl-abc",
        "object": "chat.completion",
        "model": "gpt-5-2026-01-15",     # providers often echo a dated snapshot
        "choices": [{"index": 0,
                     "message": {"role": "assistant", "content": "ANSWER: B"},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 9,
                  "total_tokens": 129},
    }
    d.update(over)
    return d


class _Resp:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _patch_http(monkeypatch, payloads, capture=None):
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        if capture is not None:
            capture["req"] = req
            capture["url"] = req.full_url
            capture["headers"] = dict(req.header_items())
            capture["body"] = json.loads(req.data.decode("utf-8"))
            capture["timeout"] = timeout
        i = min(calls["n"], len(payloads) - 1)
        calls["n"] += 1
        p = payloads[i]
        if isinstance(p, Exception):
            raise p
        return _Resp(p)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(R.time, "sleep", lambda s: None)
    return calls


def _runner(tmp_path, **rc):
    cfg = {"runner": {"backend": "claude_cli", "max_retries": 3,
                      "retry_backoff_seconds": 0, **rc}}
    return R.Runner(cfg, cache_dir=tmp_path)


def _http_error(code, msg):
    return urllib.error.HTTPError(
        "https://api.openai.com/v1/chat/completions", code, "err", {},
        io.BytesIO(json.dumps({"error": {"message": msg}}).encode("utf-8")))


# --------------------------------------------------------------------------- #
# Response parsing
# --------------------------------------------------------------------------- #


def test_success_parses_fields(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    cap = {}
    _patch_http(monkeypatch, [_oai_json()], cap)
    r = _runner(tmp_path).call("gpt-5", "sys", "prompt", "low",
                               backend="openai_compat")
    assert r.ok
    assert r.text == "ANSWER: B"
    assert r.backend == "openai_compat"
    assert r.input_tokens == 120 and r.output_tokens == 9
    assert r.stop_reason == "stop"
    assert cap["url"].endswith("/chat/completions")


def test_empty_content_is_error(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    _patch_http(monkeypatch, [_oai_json(choices=[{"index": 0, "message": {
        "role": "assistant", "content": ""}, "finish_reason": "stop"}])])
    r = _runner(tmp_path).call("gpt-5", "sys", "p", "low",
                               backend="openai_compat")
    assert not r.ok
    assert "empty result" in r.error


def test_served_mismatch_never_fires(monkeypatch, tmp_path):
    """Providers echo dated snapshots (gpt-5 -> gpt-5-2026-01-15) that don't
    match the Anthropic alias/-YYYYMMDD shape the served-guard understands.
    The backend reports model_served=None so a legitimate answer is never
    thrown away as a fallback; the echoed id is kept in served_all for audit."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    r = _runner(tmp_path)
    res = _patch_http(monkeypatch, [_oai_json()]) and r.call(
        "gpt-5", "s", "p", "low", backend="openai_compat")
    assert res.ok
    assert res.model_served is None
    assert res.served_all == "gpt-5-2026-01-15"


# --------------------------------------------------------------------------- #
# Request shape: endpoint, auth, roles, effort + extra-body passthrough
# --------------------------------------------------------------------------- #


def test_request_shape_and_bearer_auth(monkeypatch, tmp_path):
    monkeypatch.setenv("MY_KEY", "sk-secret")
    cap = {}
    _patch_http(monkeypatch, [_oai_json()], cap)
    _runner(tmp_path, openai_base_url="https://api.x.ai/v1",
            openai_api_key_env="MY_KEY").call(
        "grok-5", "SYS", "USER PROMPT", "low", backend="openai_compat")
    assert cap["url"] == "https://api.x.ai/v1/chat/completions"
    # urllib title-cases header keys
    assert cap["headers"]["Authorization"] == "Bearer sk-secret"
    body = cap["body"]
    assert body["model"] == "grok-5"
    assert body["stream"] is False
    assert body["messages"][0] == {"role": "system", "content": "SYS"}
    assert body["messages"][1] == {"role": "user", "content": "USER PROMPT"}


def test_reasoning_effort_sent_only_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    # off by default: many providers 400 on an unknown reasoning_effort field.
    # use_cache=False so the two request shapes don't share a cache entry (the
    # effort-mapping toggle is run-level config, not part of the cache key).
    cap = {}
    _patch_http(monkeypatch, [_oai_json()], cap)
    _runner(tmp_path).call("gpt-5", "s", "p", "high", backend="openai_compat",
                           use_cache=False)
    assert "reasoning_effort" not in cap["body"]
    # on when the operator opts in
    cap2 = {}
    _patch_http(monkeypatch, [_oai_json()], cap2)
    _runner(tmp_path, openai_map_effort=True).call(
        "gpt-5", "s", "p", "high", backend="openai_compat", use_cache=False)
    assert cap2["body"]["reasoning_effort"] == "high"


def test_extra_body_merged(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    cap = {}
    _patch_http(monkeypatch, [_oai_json()], cap)
    _runner(tmp_path, openai_extra_body={"temperature": 0, "max_tokens": 2048}
            ).call("gpt-5", "s", "p", "low", backend="openai_compat")
    assert cap["body"]["temperature"] == 0
    assert cap["body"]["max_tokens"] == 2048


def test_missing_api_key_fails_fast(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    calls = _patch_http(monkeypatch, [_oai_json()])
    r = _runner(tmp_path).call("gpt-5", "s", "p", "low", backend="openai_compat")
    assert not r.ok
    assert R._is_permanent_error(r.error)
    assert calls["n"] == 0            # never even attempted the HTTP call


# --------------------------------------------------------------------------- #
# Errors: permanent vs transient
# --------------------------------------------------------------------------- #


def test_bad_key_fails_fast(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-bad")
    calls = _patch_http(monkeypatch, [_http_error(401, "Incorrect API key provided")])
    r = _runner(tmp_path).call("gpt-5", "s", "p", "low", backend="openai_compat")
    assert not r.ok
    assert R._is_permanent_error(r.error)
    assert calls["n"] == 1            # permanent — no retries burned


def test_unknown_model_fails_fast(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    calls = _patch_http(monkeypatch, [_http_error(404, "The model does not exist")])
    r = _runner(tmp_path).call("nope", "s", "p", "low", backend="openai_compat")
    assert not r.ok
    assert R._is_permanent_error(r.error)
    assert calls["n"] == 1


def test_rate_limit_is_transient(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    calls = _patch_http(monkeypatch, [_http_error(429, "Rate limit reached")])
    r = _runner(tmp_path, max_retries=3).call("gpt-5", "s", "p", "low",
                                              backend="openai_compat")
    assert not r.ok
    assert not R._is_permanent_error(r.error)
    assert calls["n"] == 3            # retried to exhaustion


# --------------------------------------------------------------------------- #
# Registration + cache separation
# --------------------------------------------------------------------------- #


def test_registered_and_cache_key_separated(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert "openai_compat" in R._BACKENDS
    _patch_http(monkeypatch, [_oai_json(model="m")])
    rn = _runner(tmp_path)
    r1 = rn.call("m", "s", "p", "low", backend="openai_compat")
    assert r1.ok
    k_oai = R._cache_key("openai_compat", "m", "s", "p", "low", 0)
    k_cli = R._cache_key("claude_cli", "m", "s", "p", "low", 0)
    assert k_oai != k_cli
    assert (tmp_path / f"{k_oai}.json").exists()
    # replay from cache; no second HTTP call
    calls = _patch_http(monkeypatch, [AssertionError("must not be called")])
    r2 = rn.call("m", "s", "p", "low", backend="openai_compat")
    assert r2.cache_hit and r2.text == r1.text
    assert calls["n"] == 0
