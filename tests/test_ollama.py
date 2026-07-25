"""Ollama backend tests — urllib is always monkeypatched; no live calls.

The ollama backend serves local open-weights models (Qwen3, Gemma 3, Phi-4
Mini, SmolLM2, DeepSeek-R1 distills) through a localhost server. These tests
pin the request shape (think mapping, generation caps), the response parse,
per-call backend routing, and fail-fast semantics for unpullable models.
"""

import io
import json
import urllib.error
import urllib.request

import pytest

import deseretbench.runner as R


def _ollama_json(**over):
    d = {
        "model": "qwen3:0.6b",
        "created_at": "2026-07-08T05:00:00Z",
        "message": {"role": "assistant", "content": "ANSWER: B"},
        "done": True,
        "done_reason": "stop",
        "total_duration": 2_500_000_000,   # ns
        "prompt_eval_count": 120,
        "eval_count": 9,
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
    """payloads: list of dict | Exception, consumed per invocation."""
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        if capture is not None:
            capture["req"] = req
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


# --------------------------------------------------------------------------- #
# Response parsing
# --------------------------------------------------------------------------- #


def test_ollama_success_parses_fields(monkeypatch, tmp_path):
    cap = {}
    _patch_http(monkeypatch, [_ollama_json()], cap)
    r = _runner(tmp_path).call("qwen3:0.6b", "sys", "prompt", "low",
                               backend="ollama")
    assert r.ok
    assert r.text == "ANSWER: B"
    assert r.backend == "ollama"
    assert r.model_served == "qwen3:0.6b"
    assert r.input_tokens == 120 and r.output_tokens == 9
    assert r.stop_reason == "stop"
    assert r.duration_ms == 2500
    assert r.cost_usd == 0.0
    assert cap["req"].full_url.endswith("/api/chat")


def test_ollama_empty_content_is_error(monkeypatch, tmp_path):
    _patch_http(monkeypatch, [_ollama_json(message={"role": "assistant",
                                                    "content": ""})])
    r = _runner(tmp_path).call("qwen3:0.6b", "sys", "p", "low", backend="ollama")
    assert not r.ok
    assert "empty result" in r.error


def test_ollama_inline_think_block_stripped(monkeypatch, tmp_path):
    """Some GGUF chat templates leak reasoning as an inline <think> block.
    The Claude CLI path returns only final text; strip to stay comparable."""
    content = "<think>B or C... scripture says B.</think>\nANSWER: B"
    _patch_http(monkeypatch, [_ollama_json(
        model="deepseek-r1:1.5b",
        message={"role": "assistant", "content": content})])
    r = _runner(tmp_path).call("deepseek-r1:1.5b", "sys", "p", "low",
                               backend="ollama")
    assert r.ok
    assert "<think>" not in r.text
    assert r.text.strip() == "ANSWER: B"


def test_ollama_openerless_think_closer_stripped(monkeypatch, tmp_path):
    """Some thinking builds auto-open reasoning in their chat template, so the
    content has reasoning + a dangling </think> with NO opener (seen live on
    the qwen3:4b tag). Everything up to the last closer must be stripped."""
    content = "The user asks... B is scriptural.\n</think>\n\nANSWER: B"
    _patch_http(monkeypatch, [_ollama_json(
        model="qwen3:4b", message={"role": "assistant", "content": content})])
    r = _runner(tmp_path).call("qwen3:4b", "sys", "p", "low", backend="ollama")
    assert r.ok
    assert "</think>" not in r.text and "scriptural" not in r.text
    assert r.text.strip() == "ANSWER: B"


def test_ollama_no_think_key_for_instruct_builds(monkeypatch, tmp_path):
    """Instruct-tagged qwen3 builds have no think mode; sending the key 400s.
    Family match must not fire on '-instruct' ids."""
    cap = {}
    _patch_http(monkeypatch, [_ollama_json(model="qwen3:4b-instruct")], cap)
    _runner(tmp_path).call("qwen3:4b-instruct", "sys", "p", "high",
                           backend="ollama")
    assert "think" not in cap["body"]


def test_ollama_separate_thinking_field_ignored(monkeypatch, tmp_path):
    """When the server parses thinking natively it arrives in message.thinking;
    only message.content is the measured answer."""
    _patch_http(monkeypatch, [_ollama_json(model="qwen3:1.7b", message={
        "role": "assistant", "content": "ANSWER: C",
        "thinking": "let me reason at length..."})])
    r = _runner(tmp_path).call("qwen3:1.7b", "sys", "p", "high", backend="ollama")
    assert r.ok and r.text == "ANSWER: C"
    assert "reason at length" not in r.text


# --------------------------------------------------------------------------- #
# Request shape: think mapping mirrors the effort knob (MC=low → off,
# open=high → on), generation caps always present
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("model,effort,expected", [
    ("qwen3:4b", "low", False),
    ("qwen3:4b", "high", True),
    ("deepseek-r1:1.5b", "low", False),
    ("deepseek-r1:1.5b", "high", True),
    # 2026 cohort additions: all reason by default, so the key must be sent or
    # they burn the whole num_predict budget on reasoning and return no answer.
    # qwen3.5 has NO -instruct tag published; the top-level `think` field on
    # /api/chat is its only working control surface.
    ("qwen3.5:4b", "low", False),
    ("qwen3.5:4b", "high", True),
    ("nemotron-3-nano:4b", "low", False),
    ("nemotron-3-nano:4b", "high", True),
    ("gemma4:e2b-it-qat", "low", False),
    ("gemma4:e2b-it-qat", "high", True),
])
def test_ollama_think_toggle_for_think_families(monkeypatch, tmp_path,
                                                model, effort, expected):
    cap = {}
    _patch_http(monkeypatch, [_ollama_json(model=model)], cap)
    _runner(tmp_path).call(model, "sys", "p", effort, backend="ollama")
    assert cap["body"]["think"] is expected


@pytest.mark.parametrize("model", [
    "gemma3:1b", "phi4-mini", "smollm2:1.7b",
    # gemma3 must stay excluded even though "gemma4" is now a think family —
    # a bare "gemma" entry would match it here and 400 the call.
    "gemma3:4b",
    # 2026 additions with no reasoning mode: IBM Granite lists five
    # capabilities and reasoning is not among them; Mistral ships reasoning as
    # a separate repo, so every ministral-3 tag is an instruct build.
    "granite4.1:3b", "ministral-3:3b",
])
def test_ollama_no_think_key_for_non_think_models(monkeypatch, tmp_path, model):
    cap = {}
    _patch_http(monkeypatch, [_ollama_json(model=model)], cap)
    _runner(tmp_path).call(model, "sys", "p", "high", backend="ollama")
    assert "think" not in cap["body"]


def test_ollama_request_shape(monkeypatch, tmp_path):
    cap = {}
    _patch_http(monkeypatch, [_ollama_json()], cap)
    _runner(tmp_path).call("qwen3:0.6b", "SYS", "USER PROMPT", "low",
                           backend="ollama")
    body = cap["body"]
    assert body["stream"] is False
    assert body["messages"][0] == {"role": "system", "content": "SYS"}
    assert body["messages"][1] == {"role": "user", "content": "USER PROMPT"}
    # runaway-generation and context caps are always pinned
    assert body["options"]["num_predict"] == 4096
    assert body["options"]["num_ctx"] == 8192


# --------------------------------------------------------------------------- #
# Errors: permanent vs transient
# --------------------------------------------------------------------------- #


def _http_error(code, msg):
    return urllib.error.HTTPError(
        "http://localhost:11434/api/chat", code, "err", {},
        io.BytesIO(json.dumps({"error": msg}).encode("utf-8")))


def test_ollama_model_not_pulled_fails_fast(monkeypatch, tmp_path):
    calls = _patch_http(monkeypatch, [
        _http_error(404, 'model "nope:1b" not found, try pulling it first')])
    r = _runner(tmp_path).call("nope:1b", "sys", "p", "low", backend="ollama")
    assert not r.ok
    assert "try pulling" in r.error
    assert calls["n"] == 1          # permanent — no retries burned
    assert R._is_permanent_error(r.error)


def test_ollama_server_down_is_transient(monkeypatch, tmp_path):
    calls = _patch_http(monkeypatch, [
        urllib.error.URLError(ConnectionRefusedError(111, "refused"))])
    r = _runner(tmp_path, max_retries=3).call("qwen3:0.6b", "s", "p", "low",
                                              backend="ollama")
    assert not r.ok
    assert not R._is_permanent_error(r.error)
    assert calls["n"] == 3          # retried to exhaustion


def test_ollama_timeout_is_transient(monkeypatch, tmp_path):
    calls = _patch_http(monkeypatch, [TimeoutError("timed out")])
    r = _runner(tmp_path, max_retries=2).call("qwen3:4b", "s", "p", "high",
                                              backend="ollama")
    assert not r.ok
    assert "timeout" in r.error.lower()
    assert not R._is_permanent_error(r.error)
    assert calls["n"] == 2


# --------------------------------------------------------------------------- #
# Per-call backend routing + cache-key separation
# --------------------------------------------------------------------------- #


def test_backend_routing_and_cache_key_separation(monkeypatch, tmp_path):
    """The same (model, system, prompt, effort, run) under a different backend
    must be a different cache entry — Claude entries stay untouched."""
    _patch_http(monkeypatch, [_ollama_json(model="m")])
    rn = _runner(tmp_path)
    r1 = rn.call("m", "s", "p", "low", backend="ollama")
    assert r1.ok and r1.backend == "ollama"

    k_ollama = R._cache_key("ollama", "m", "s", "p", "low", 0)
    k_cli = R._cache_key("claude_cli", "m", "s", "p", "low", 0)
    assert k_ollama != k_cli
    assert (tmp_path / f"{k_ollama}.json").exists()
    assert not (tmp_path / f"{k_cli}.json").exists()

    # replay comes from cache (urlopen not called again)
    calls = _patch_http(monkeypatch, [AssertionError("must not be called")])
    r2 = rn.call("m", "s", "p", "low", backend="ollama")
    assert r2.cache_hit and r2.text == r1.text
    assert calls["n"] == 0


def test_map_passes_backend_through(monkeypatch, tmp_path):
    _patch_http(monkeypatch, [_ollama_json()])
    rn = _runner(tmp_path, max_parallel=1)
    res = rn.map([{"model": "qwen3:0.6b", "system": "s", "prompt": "p",
                   "effort": "low", "run_index": 0, "backend": "ollama"}])
    assert res[0].ok and res[0].backend == "ollama"


def test_ollama_served_mismatch_fails_fast(monkeypatch, tmp_path):
    """The served-model guard covers the ollama backend too: if the server
    answers with a different model than requested, that's a permanent error."""
    calls = _patch_http(monkeypatch, [_ollama_json(model="other:2b")])
    r = _runner(tmp_path).call("qwen3:0.6b", "s", "p", "low", backend="ollama")
    assert not r.ok
    assert "served_mismatch" in r.error
    assert calls["n"] == 1


def test_default_backend_unchanged_without_override(monkeypatch, tmp_path):
    """No backend key in the job → the configured default (claude_cli) runs."""
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        raise FileNotFoundError()

    monkeypatch.setattr(R.subprocess, "run", fake_run)
    r = _runner(tmp_path).call("claude-opus-4-8", "s", "p", "low")
    assert r.backend == "claude_cli"
    assert seen["cmd"][0] == "claude"
