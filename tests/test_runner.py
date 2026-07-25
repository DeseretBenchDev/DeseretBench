"""Runner behavior tests — subprocess is always monkeypatched; no live calls."""

import json
import re

import pytest

import deseretbench.runner as R


def _cli_json(**over):
    d = {
        "is_error": False,
        "result": "42",
        "modelUsage": {"claude-opus-4-7": {"outputTokens": 9, "costUSD": 0.01}},
        "usage": {
            "input_tokens": 6,
            "output_tokens": 9,
            "cache_read_input_tokens": 1700,
            "cache_creation_input_tokens": 100,
        },
        "total_cost_usd": 0.01,
        "duration_ms": 800,
        "stop_reason": "end_turn",
    }
    d.update(over)
    return d


class _Proc:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _patch_cli(monkeypatch, payloads, capture=None):
    """payloads: list of _Proc or Exception, consumed per invocation."""
    calls = {"n": 0}

    def fake_run(cmd, **kw):
        if capture is not None:
            capture["cmd"] = cmd
            capture["kwargs"] = kw
        i = min(calls["n"], len(payloads) - 1)
        calls["n"] += 1
        p = payloads[i]
        if isinstance(p, Exception):
            raise p
        return p

    monkeypatch.setattr(R.subprocess, "run", fake_run)
    monkeypatch.setattr(R.time, "sleep", lambda s: None)
    return calls


def _runner(tmp_path, **rc):
    cfg = {"runner": {"backend": "claude_cli", "max_retries": 3,
                      "retry_backoff_seconds": 0, **rc}}
    return R.Runner(cfg, cache_dir=tmp_path)


# --------------------------------------------------------------------------- #
# transport safety
# --------------------------------------------------------------------------- #

def test_prompt_via_stdin_not_argv(tmp_path, monkeypatch):
    """Item text must never enter argv (option-injection + ps leakage)."""
    cap = {}
    _patch_cli(monkeypatch, [_Proc(stdout=json.dumps(_cli_json()))], cap)
    evil = "--mcp-config {\"evil\": true}"
    _runner(tmp_path).call("claude-opus-4-7", "sys", evil, "low", use_cache=False)
    assert evil not in cap["cmd"]
    assert cap["kwargs"].get("input") == evil


def test_filenotfound_is_clean_failure(tmp_path, monkeypatch):
    calls = _patch_cli(monkeypatch, [FileNotFoundError("claude")])
    r = _runner(tmp_path).call("m", "s", "p", "low", use_cache=False)
    assert r.ok is False
    assert "not found" in r.error.lower()
    assert calls["n"] == 1  # permanent — no retries


# --------------------------------------------------------------------------- #
# error semantics
# --------------------------------------------------------------------------- #

def test_empty_text_sets_descriptive_error(tmp_path, monkeypatch):
    _patch_cli(monkeypatch, [_Proc(stdout=json.dumps(
        _cli_json(result="", stop_reason="max_tokens")))])
    r = _runner(tmp_path, max_retries=1).call("claude-opus-4-7", "s", "p", "low",
                                              use_cache=False)
    assert r.ok is False
    assert r.error and "empty result" in r.error and "max_tokens" in r.error


def test_permanent_cli_error_fails_fast(tmp_path, monkeypatch):
    calls = _patch_cli(monkeypatch, [_Proc(stdout="", stderr="Error: model not found",
                                           returncode=1)])
    r = _runner(tmp_path).call("claude-bogus", "s", "p", "low", use_cache=False)
    assert r.ok is False
    assert calls["n"] == 1


def test_transient_error_still_retries(tmp_path, monkeypatch):
    calls = _patch_cli(monkeypatch, [_Proc(stdout="oops not json")])
    r = _runner(tmp_path).call("m", "s", "p", "low", use_cache=False)
    assert r.ok is False
    assert calls["n"] == 3


# --------------------------------------------------------------------------- #
# provenance
# --------------------------------------------------------------------------- #

def test_multikey_modelusage_picks_dominant(tmp_path, monkeypatch):
    mu = {
        "claude-haiku-4-5-20251001": {"outputTokens": 3, "costUSD": 0.0001},
        "claude-opus-4-7": {"outputTokens": 500, "costUSD": 0.011},
    }
    _patch_cli(monkeypatch, [_Proc(stdout=json.dumps(_cli_json(modelUsage=mu)))])
    r = _runner(tmp_path).call("claude-opus-4-7", "s", "p", "low", use_cache=False)
    assert r.ok is True
    assert r.model_served == "claude-opus-4-7"
    assert "claude-haiku-4-5-20251001" in (r.served_all or "")


def test_true_served_mismatch_is_failure(tmp_path, monkeypatch):
    mu = {"claude-haiku-4-5-20251001": {"outputTokens": 9, "costUSD": 0.001}}
    _patch_cli(monkeypatch, [_Proc(stdout=json.dumps(_cli_json(modelUsage=mu)))])
    r = _runner(tmp_path, max_retries=1).call("claude-opus-4-7", "s", "p", "low",
                                              use_cache=False)
    assert r.ok is False
    assert "served_mismatch" in r.error


def test_cache_read_rejects_served_mismatch(tmp_path, monkeypatch):
    run = _runner(tmp_path)
    key = R._cache_key("claude_cli", "claude-opus-4-7", "s", "p", "low", 0)
    stale = {"ok": True, "text": "x", "model_requested": "claude-opus-4-7",
             "model_served": "claude-haiku-4-5-20251001", "effort": "low"}
    (tmp_path / f"{key}.json").write_text(json.dumps(stale))
    _patch_cli(monkeypatch, [_Proc(stdout=json.dumps(_cli_json()))])
    r = run.call("claude-opus-4-7", "s", "p", "low")
    assert r.cache_hit is False
    assert r.model_served == "claude-opus-4-7"


def test_called_at_timestamp_recorded(tmp_path, monkeypatch):
    _patch_cli(monkeypatch, [_Proc(stdout=json.dumps(_cli_json()))])
    r = _runner(tmp_path).call("claude-opus-4-7", "s", "p", "low", use_cache=False)
    assert r.called_at and re.match(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ", r.called_at)


def test_legacy_cache_entry_still_loads(tmp_path, monkeypatch):
    """v0.1 cache entries lack the new fields; they must still deserialize."""
    run = _runner(tmp_path)
    key = R._cache_key("claude_cli", "m", "s", "p", "low", 0)
    legacy = {"ok": True, "text": "x", "model_requested": "m", "model_served": "m",
              "effort": "low", "input_tokens": 6, "output_tokens": 9,
              "cost_usd": 0.01, "duration_ms": 1, "stop_reason": "end_turn",
              "error": None, "backend": "claude_cli", "attempts": 1,
              "cache_hit": False}
    (tmp_path / f"{key}.json").write_text(json.dumps(legacy))
    r = run.call("m", "s", "p", "low")
    assert r.cache_hit is True and r.text == "x"


# --------------------------------------------------------------------------- #
# accounting
# --------------------------------------------------------------------------- #

def test_token_cache_fields_captured(tmp_path, monkeypatch):
    _patch_cli(monkeypatch, [_Proc(stdout=json.dumps(_cli_json()))])
    r = _runner(tmp_path).call("claude-opus-4-7", "s", "p", "low", use_cache=False)
    assert r.cache_read_input_tokens == 1700
    assert r.cache_creation_input_tokens == 100


def test_spend_accumulates_across_attempts(tmp_path, monkeypatch):
    fail = _cli_json(is_error=True, result="", total_cost_usd=0.02)
    ok = _cli_json(total_cost_usd=0.03)
    _patch_cli(monkeypatch, [_Proc(stdout=json.dumps(fail)),
                             _Proc(stdout=json.dumps(ok))])
    run = _runner(tmp_path)
    r = run.call("claude-opus-4-7", "s", "p", "low", use_cache=False)
    assert r.ok is True
    assert run.total_spend_usd == pytest.approx(0.05)


# --------------------------------------------------------------------------- #
# config plumbing
# --------------------------------------------------------------------------- #

def test_cli_flags_come_from_config(tmp_path, monkeypatch):
    cap = {}
    _patch_cli(monkeypatch, [_Proc(stdout=json.dumps(_cli_json()))], cap)
    cfg = {"runner": {"backend": "claude_cli", "max_retries": 1,
                      "retry_backoff_seconds": 0, "tools": "",
                      "no_session_persistence": True}}
    R.Runner(cfg, cache_dir=tmp_path).call("claude-opus-4-7", "s", "p", "low",
                                           use_cache=False)
    cmd = cap["cmd"]
    assert cmd[cmd.index("--tools") + 1] == ""
    assert "--no-session-persistence" in cmd


def test_api_reasoning_params_per_model():
    """4.6+ models reject budget_tokens (adaptive + effort); older ones keep it."""
    p_new = R._api_reasoning_params("claude-opus-4-8", "high")
    assert p_new.get("thinking", {}).get("type") == "adaptive"
    assert p_new.get("output_config", {}).get("effort") == "high"
    # xhigh exists only on opus-4-7+; clamp on 4.6-family
    p_46 = R._api_reasoning_params("claude-opus-4-6", "xhigh")
    assert p_46["output_config"]["effort"] == "high"
    # pre-4.6 models: budget_tokens path, no effort param (errors there)
    p_old = R._api_reasoning_params("claude-sonnet-4-5-20250929", "high")
    assert p_old.get("thinking", {}).get("budget_tokens")
    assert "output_config" not in p_old
    p_haiku = R._api_reasoning_params("claude-haiku-4-5-20251001", "low")
    assert p_haiku.get("thinking", {}).get("budget_tokens")


# --------------------------------------------------------------------------- #
# regressions caught by the audit's adversarial review round
# --------------------------------------------------------------------------- #

def test_served_matches_only_dated_suffix():
    assert R._served_matches("claude-opus-4-8", "claude-opus-4-8")
    assert R._served_matches("claude-haiku-4-5", "claude-haiku-4-5-20251001")
    assert R._served_matches("claude-haiku-4-5-20251001", "claude-haiku-4-5")
    # tier/variant suffixes and shared prefixes are REAL mismatches
    assert not R._served_matches("claude-opus-4-8", "claude-opus-4-8-fast")
    assert not R._served_matches("claude-opus-4-8-fast", "claude-opus-4-8")
    assert not R._served_matches("claude-opus-4", "claude-opus-4-6")
    assert not R._served_matches("claude-opus-4-7", "claude-haiku-4-5-20251001")


def test_served_mismatch_fails_fast(tmp_path, monkeypatch):
    mu = {"claude-haiku-4-5-20251001": {"outputTokens": 9, "costUSD": 0.001}}
    calls = _patch_cli(monkeypatch, [_Proc(stdout=json.dumps(_cli_json(modelUsage=mu)))])
    run = _runner(tmp_path)  # max_retries=3
    r = run.call("claude-opus-4-7", "s", "p", "low", use_cache=False)
    assert r.ok is False and "served_mismatch" in r.error
    assert calls["n"] == 1  # deterministic while the fallback persists — one paid attempt


def test_numeric_api_error_status_does_not_crash(tmp_path, monkeypatch):
    _patch_cli(monkeypatch, [_Proc(stdout=json.dumps(
        _cli_json(is_error=False, api_error_status=429, result="")))])
    r = _runner(tmp_path).call("m", "s", "p", "low", use_cache=False)
    assert r.ok is False and r.error == "429"


def test_transient_not_found_phrases_still_retry(tmp_path, monkeypatch):
    calls = _patch_cli(monkeypatch, [_Proc(stdout="", stderr="error: session not found, retry",
                                           returncode=1)])
    r = _runner(tmp_path).call("m", "s", "p", "low", use_cache=False)
    assert r.ok is False
    assert calls["n"] == 3  # generic 'not found' no longer counts as permanent


def test_opus_4_5_uses_budget_tokens_path():
    p = R._api_reasoning_params("claude-opus-4-5", "high")
    assert p.get("thinking", {}).get("budget_tokens")
    assert "output_config" not in p


# --------------------------------------------------------------------------- #
# Operator-settings isolation (ADR-0012)
# --------------------------------------------------------------------------- #


def _capture_cmd(monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        raise FileNotFoundError()      # short-circuit; we only inspect argv

    monkeypatch.setattr(R.subprocess, "run", fake_run)
    return seen


def _cli_runner(tmp_path):
    return R.Runner({"runner": {"backend": "claude_cli", "max_retries": 1,
                                "retry_backoff_seconds": 0}}, cache_dir=tmp_path)


def test_cli_pins_advisor_model_to_the_requested_model(monkeypatch, tmp_path):
    """The CLI reads the operator's settings.json. If that sets an advisorModel
    of a different family, its tokens land in the same modelUsage map and can
    outweigh the answer's, flipping attribution and tripping the served-model
    guard. Pin the advisor to the model under test so a benchmark's behaviour
    follows from its committed config, not from whoever is running it."""
    seen = _capture_cmd(monkeypatch)
    _cli_runner(tmp_path).call("claude-sonnet-4-6", "sys", "p", "medium")
    cmd = seen["cmd"]
    assert "--settings" in cmd
    payload = json.loads(cmd[cmd.index("--settings") + 1])
    assert payload["advisorModel"] == "claude-sonnet-4-6"


def test_cli_settings_isolation_follows_the_model_under_test(monkeypatch, tmp_path):
    seen = _capture_cmd(monkeypatch)
    _cli_runner(tmp_path).call("claude-opus-4-8", "sys", "p", "low")
    cmd = seen["cmd"]
    payload = json.loads(cmd[cmd.index("--settings") + 1])
    assert payload["advisorModel"] == "claude-opus-4-8"
