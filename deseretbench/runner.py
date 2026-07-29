"""Model runner for DeseretBench.

Provider-agnostic interface with two backends:
  * ``claude_cli``     — invokes the authenticated `claude` CLI (default; used in
                          environments without a raw API key).
  * ``anthropic_api``  — canonical reproducible path for researchers who export
                          ANTHROPIC_API_KEY (see REPRODUCE.md). Stub-importable;
                          only loads the SDK when selected.

Design goals:
  * **Resume-safe**: every call is content-addressed and cached on disk, so a
    re-run skips completed work and only fills gaps.
  * **Honest provenance**: records the model the API *actually served* (guards
    against silent fallback), token usage, cost, latency, stop reason.
  * **Robust**: retries transient failures with backoff (permanent errors fail
    fast); never invokes a shell, and item text is passed via stdin / SDK args,
    so it can never be parsed as a CLI option or leak into `ps` output.
"""

from __future__ import annotations

import concurrent.futures as cf
import dataclasses
import hashlib
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Iterable, Optional

# --------------------------------------------------------------------------- #
# Result type
# --------------------------------------------------------------------------- #


@dataclasses.dataclass
class CallResult:
    ok: bool
    text: str                      # the model's answer text (d["result"])
    model_requested: str
    model_served: Optional[str]    # from modelUsage; None if unknown
    effort: str
    input_tokens: int = 0                  # uncached input slice only (see cache_* fields)
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    stop_reason: Optional[str] = None
    error: Optional[str] = None
    backend: str = "claude_cli"
    attempts: int = 1
    cache_hit: bool = False
    served_all: Optional[str] = None       # comma-joined modelUsage keys when >1 model reported
    provider_model: Optional[str] = None   # id a non-Anthropic provider echoed (openai_compat)
    called_at: Optional[str] = None        # UTC wall-clock of the live call (audit vs alias repoints)
    raw: Optional[dict] = None

    def to_json(self) -> dict:
        d = dataclasses.asdict(self)
        # keep cache files compact: drop the bulky raw blob on disk
        d.pop("raw", None)
        return d


# --------------------------------------------------------------------------- #
# Cache (content-addressed)
# --------------------------------------------------------------------------- #


def _cache_key(backend: str, model: str, system: str, prompt: str,
               effort: str, run_index: int) -> str:
    h = hashlib.sha256()
    payload = json.dumps(
        {"b": backend, "m": model, "s": system, "p": prompt,
         "e": effort, "r": run_index},
        sort_keys=True, ensure_ascii=False,
    )
    h.update(payload.encode("utf-8"))
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# CLI backend
# --------------------------------------------------------------------------- #


def _dominant_model(mu: dict) -> tuple[Optional[str], Optional[str]]:
    """Pick the primary serving model from a modelUsage map.

    The CLI sometimes reports auxiliary sub-model calls (e.g. a haiku helper)
    alongside the primary model; dict order is arbitrary, so choose the key
    with the most output tokens / cost and record all keys when there are >1.
    """
    if not mu:
        return None, None
    keys = list(mu.keys())
    if len(keys) == 1:
        return keys[0], None

    def usage_weight(k: str) -> tuple:
        v = mu.get(k)
        if not isinstance(v, dict):
            return (0, 0.0)
        return (v.get("outputTokens", 0) or 0, v.get("costUSD", 0.0) or 0.0)

    return max(keys, key=usage_weight), ",".join(keys)


def _call_cli(model: str, system: str, prompt: str, effort: str,
              timeout: int, opts: Optional[dict] = None) -> CallResult:
    opts = opts or {}
    # Prompt goes over stdin, never argv: item text can't be parsed as a CLI
    # option, can't exceed the argv size limit, and never shows up in `ps`.
    # The CLI reads the operator's ~/.claude/settings.json. An advisorModel set
    # there is consulted on hard prompts and its tokens land in the same
    # modelUsage map as the answer's, so a big enough advisor turn flips
    # _dominant_model to a model we never asked for (ADR-0012). Pin the advisor
    # to the model under test: a benchmark's behaviour must follow from its
    # committed config, not from whoever happens to be running it.
    cmd = [
        "claude", "-p",
        "--model", model,
        "--tools", opts.get("tools", ""),
        "--system-prompt", system,
        "--output-format", "json",
        "--effort", effort,
        "--settings", json.dumps({"advisorModel": model}),
    ]
    if opts.get("no_session_persistence", True):
        cmd.append("--no-session-persistence")
    try:
        proc = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return CallResult(ok=False, text="", model_requested=model,
                          model_served=None, effort=effort,
                          error=f"timeout>{timeout}s", backend="claude_cli")
    except FileNotFoundError:
        return CallResult(ok=False, text="", model_requested=model,
                          model_served=None, effort=effort,
                          error="claude CLI not found on PATH", backend="claude_cli")
    except OSError as e:
        return CallResult(ok=False, text="", model_requested=model,
                          model_served=None, effort=effort,
                          error=f"os error launching claude CLI: {e}",
                          backend="claude_cli")

    if proc.returncode != 0 and not proc.stdout.strip():
        return CallResult(ok=False, text="", model_requested=model,
                          model_served=None, effort=effort,
                          error=f"exit={proc.returncode}: {proc.stderr.strip()[:300]}",
                          backend="claude_cli")
    try:
        d = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return CallResult(ok=False, text="", model_requested=model,
                          model_served=None, effort=effort,
                          error=f"non-json stdout: {proc.stdout.strip()[:300]}",
                          backend="claude_cli")

    is_err = bool(d.get("is_error")) or d.get("api_error_status") is not None
    served, served_all = _dominant_model(d.get("modelUsage") or {})
    usage = d.get("usage") or {}
    text = d.get("result") or ""

    # api_error_status may arrive as a number — CallResult.error is Optional[str]
    status = d.get("api_error_status")
    error = (str(status) if status is not None
             else ("is_error" if is_err else None))
    if error is None and not text:
        error = f"empty result (stop_reason={d.get('stop_reason')})"

    return CallResult(
        ok=not is_err and bool(text),
        text=text,
        model_requested=model,
        model_served=served,
        effort=effort,
        input_tokens=int(usage.get("input_tokens", 0) or 0),
        output_tokens=int(usage.get("output_tokens", 0) or 0),
        cache_creation_input_tokens=int(usage.get("cache_creation_input_tokens", 0) or 0),
        cache_read_input_tokens=int(usage.get("cache_read_input_tokens", 0) or 0),
        cost_usd=float(d.get("total_cost_usd", 0.0) or 0.0),
        duration_ms=int(d.get("duration_ms", 0) or 0),
        stop_reason=d.get("stop_reason"),
        error=error,
        backend="claude_cli",
        served_all=served_all,
        raw=d,
    )


# --------------------------------------------------------------------------- #
# API backend (canonical reproducible path; loaded lazily)
# --------------------------------------------------------------------------- #


_EFFORT_TO_THINKING = {  # budget mapping for pre-4.6 models only
    "low": 2048, "medium": 6144, "high": 16384, "xhigh": 32768, "max": 60000,
}

# Model families that take adaptive thinking + output_config.effort.
# budget_tokens is REJECTED (400) on opus-4-7/4-8 and deprecated on the 4.6
# family; pre-4.6 models (opus-4-5, sonnet-4-5, haiku-4-5) use the
# budget_tokens path — adaptive thinking would 400 there. (Opus 4.5 does
# accept the effort parameter, but we keep it on the uniform budget path.)
_ADAPTIVE_FAMILIES = ("opus-4-8", "opus-4-7", "opus-4-6",
                      "sonnet-4-6", "sonnet-5", "fable-5", "mythos")
_XHIGH_FAMILIES = ("opus-4-8", "opus-4-7", "sonnet-5", "fable-5", "mythos")


def _api_reasoning_params(model: str, effort: str) -> dict:
    """Per-model-valid reasoning config for the Messages API."""
    if any(f in model for f in _ADAPTIVE_FAMILIES):
        eff = effort
        if eff == "xhigh" and not any(f in model for f in _XHIGH_FAMILIES):
            eff = "high"  # xhigh only exists on opus-4-7 and later
        params: dict = {
            "output_config": {"effort": eff},
            "max_tokens": 32000,
        }
        if not any(f in model for f in ("fable-5", "mythos")):
            # fable/mythos: thinking always on, param must be omitted
            params["thinking"] = {"type": "adaptive"}
        return params
    budget = _EFFORT_TO_THINKING.get(effort, 4096)
    return {
        "thinking": {"type": "enabled", "budget_tokens": budget},
        "max_tokens": budget + 4096,
    }


def _call_api(model: str, system: str, prompt: str, effort: str,
              timeout: int, opts: Optional[dict] = None) -> CallResult:
    try:
        import anthropic  # noqa
    except Exception as e:  # pragma: no cover
        return CallResult(ok=False, text="", model_requested=model,
                          model_served=None, effort=effort,
                          error=f"anthropic SDK not installed: {e}",
                          backend="anthropic_api")
    client = anthropic.Anthropic()
    try:
        msg = client.messages.create(
            model=model,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            timeout=timeout,
            **_api_reasoning_params(model, effort),
        )
    except Exception as e:  # pragma: no cover
        return CallResult(ok=False, text="", model_requested=model,
                          model_served=None, effort=effort,
                          error=f"api error: {e}", backend="anthropic_api")
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    usage = getattr(msg, "usage", None)
    stop_reason = getattr(msg, "stop_reason", None)
    return CallResult(
        ok=bool(text), text=text, model_requested=model,
        model_served=getattr(msg, "model", model), effort=effort,
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
        output_tokens=getattr(usage, "output_tokens", 0) or 0,
        cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
        cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
        stop_reason=stop_reason,
        error=None if text else f"empty result (stop_reason={stop_reason})",
        backend="anthropic_api", raw=None,
    )


# --------------------------------------------------------------------------- #
# Ollama backend (local open-weights models on localhost; no key, zero cost)
# --------------------------------------------------------------------------- #

# Families with a toggleable native think mode. The effort knob maps onto it
# (low → off, medium/high → on), mirroring how the Claude cohort's effort was
# pinned per item class (MC=low, open=high). Non-listed models never get the
# key — ollama 400s on models without think support. "-instruct" builds of a
# think family are non-thinking siblings and must not get the key either.
# Families whose ollama builds reason by default and therefore need an explicit
# `think` key. Matching is substring-on-the-tag, which is why the entries are
# exact about generation: "qwen3" also covers "qwen3.5:*" (same toggle), but the
# Gemma entry MUST be "gemma4" — a bare "gemma" would also match the
# non-thinking gemma3 builds, where sending the key 400s.
_OLLAMA_THINK_FAMILIES = ("qwen3", "deepseek-r1", "nemotron", "gemma4")


def _wants_think_key(model: str) -> bool:
    return (any(f in model for f in _OLLAMA_THINK_FAMILIES)
            and "instruct" not in model)


# Some GGUF chat templates leak reasoning into content instead of the API's
# separate `thinking` field — either as a full <think>…</think> block, or
# (when the template auto-opens thinking, as the qwen3:4b tag does) as bare
# reasoning ending in a dangling </think> with no opener. The Claude CLI path
# returns only final answer text, so strip everything through the LAST closer
# to keep the measured surface comparable across backends.
def _strip_think(text: str) -> str:
    if "</think>" in text:
        return text.rsplit("</think>", 1)[-1].strip()
    return text.strip()


def _call_ollama(model: str, system: str, prompt: str, effort: str,
                 timeout: int, opts: Optional[dict] = None) -> CallResult:
    import urllib.error
    import urllib.request
    opts = opts or {}
    host = (opts.get("ollama_host") or "http://localhost:11434").rstrip("/")
    body: dict = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": prompt}],
        "stream": False,
        # pinned generation caps: bound runaway reasoning loops and keep the
        # KV cache small enough for one-model-at-a-time CPU serving
        "options": {"num_predict": int(opts.get("ollama_num_predict", 4096)),
                    "num_ctx": int(opts.get("ollama_num_ctx", 8192))},
    }
    if _wants_think_key(model):
        body["think"] = effort != "low"
    req = urllib.request.Request(
        f"{host}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            d = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("error", "")
        except Exception:
            msg = ""
        return CallResult(ok=False, text="", model_requested=model,
                          model_served=None, effort=effort,
                          error=f"ollama http {e.code}: {str(msg)[:300]}",
                          backend="ollama")
    except TimeoutError:
        return CallResult(ok=False, text="", model_requested=model,
                          model_served=None, effort=effort,
                          error=f"timeout>{timeout}s", backend="ollama")
    except (urllib.error.URLError, OSError) as e:
        # covers connection-refused (server restarting) and socket timeouts
        # wrapped in URLError — both transient, both retried
        reason = getattr(e, "reason", e)
        err = (f"timeout>{timeout}s" if "timed out" in str(reason).lower()
               else f"ollama unreachable: {reason}")
        return CallResult(ok=False, text="", model_requested=model,
                          model_served=None, effort=effort,
                          error=err, backend="ollama")
    except json.JSONDecodeError as e:
        return CallResult(ok=False, text="", model_requested=model,
                          model_served=None, effort=effort,
                          error=f"ollama non-json response: {e}", backend="ollama")

    msg_obj = d.get("message") or {}
    text = _strip_think(msg_obj.get("content") or "")
    stop = d.get("done_reason")
    error = d.get("error")
    if error is None and not text:
        error = f"empty result (stop_reason={stop})"
    return CallResult(
        ok=error is None and bool(text),
        text=text,
        model_requested=model,
        model_served=d.get("model"),
        effort=effort,
        input_tokens=int(d.get("prompt_eval_count", 0) or 0),
        output_tokens=int(d.get("eval_count", 0) or 0),
        cost_usd=0.0,                     # local inference: no marginal cost
        duration_ms=int((d.get("total_duration", 0) or 0) / 1e6),
        stop_reason=stop,
        error=str(error) if error is not None else None,
        backend="ollama",
        raw=d,
    )


# --------------------------------------------------------------------------- #
# OpenAI-compatible backend
# --------------------------------------------------------------------------- #
# Any endpoint that speaks OpenAI's /chat/completions: OpenAI, xAI Grok,
# DeepSeek, Zhipu GLM, Moonshot Kimi, OpenRouter, Together, or a local proxy.
# One backend covers all of them — the base URL and the API-key env var are
# configured (run_config runner.openai_*), and a cohort entry just carries
# `backend: openai_compat` with the provider's model id. Uses urllib, so it
# adds no dependency; an API key is required (subscription-only providers need
# a proxy that exchanges the session for a key — see docs/how-to/run-any-model).

# effort -> OpenAI `reasoning_effort`, sent ONLY when openai_map_effort is set:
# many providers reject an unrecognised field with a 400, so it is opt-in.
_OPENAI_EFFORT = {"low": "low", "medium": "medium", "high": "high",
                  "xhigh": "high", "max": "high"}


def _call_openai_compat(model: str, system: str, prompt: str, effort: str,
                        timeout: int, opts: Optional[dict] = None) -> CallResult:
    import urllib.error
    import urllib.request
    opts = opts or {}
    base = (opts.get("openai_base_url") or "https://api.openai.com/v1").rstrip("/")
    key_env = opts.get("openai_api_key_env") or "OPENAI_API_KEY"
    key = os.environ.get(key_env, "")
    if not key:
        # No credential -> permanent (retrying can't conjure one). The message
        # names the exact env var so the fix is obvious; "authentication" makes
        # it fail-fast via _PERMANENT_ERROR_MARKERS.
        return CallResult(ok=False, text="", model_requested=model,
                          model_served=None, effort=effort,
                          error=f"authentication: ${key_env} is not set",
                          backend="openai_compat")
    body: dict = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": prompt}],
        "stream": False,
    }
    extra = opts.get("openai_extra_body")
    if isinstance(extra, dict):
        body.update(extra)   # operator-supplied params (temperature, max_tokens…)
    if opts.get("openai_map_effort") and "reasoning_effort" not in body:
        body["reasoning_effort"] = _OPENAI_EFFORT.get(effort, "medium")
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            d = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8"))
            err_obj = payload.get("error")
            msg = (err_obj.get("message") if isinstance(err_obj, dict)
                   else err_obj) or ""
        except Exception:
            msg = ""
        # 400/401/403/404 are config errors (bad key, unknown model, rejected
        # param) that will not heal on retry; 429 and 5xx stay transient. The
        # "openai http <code>" prefix is what _PERMANENT_ERROR_MARKERS keys on.
        return CallResult(ok=False, text="", model_requested=model,
                          model_served=None, effort=effort,
                          error=f"openai http {e.code}: {str(msg)[:300]}",
                          backend="openai_compat")
    except TimeoutError:
        return CallResult(ok=False, text="", model_requested=model,
                          model_served=None, effort=effort,
                          error=f"timeout>{timeout}s", backend="openai_compat")
    except (urllib.error.URLError, OSError) as e:
        reason = getattr(e, "reason", e)
        err = (f"timeout>{timeout}s" if "timed out" in str(reason).lower()
               else f"provider unreachable: {reason}")
        return CallResult(ok=False, text="", model_requested=model,
                          model_served=None, effort=effort,
                          error=err, backend="openai_compat")
    except json.JSONDecodeError as e:
        return CallResult(ok=False, text="", model_requested=model,
                          model_served=None, effort=effort,
                          error=f"provider non-json response: {e}",
                          backend="openai_compat")

    choices = d.get("choices") or []
    msg_obj = (choices[0].get("message") or {}) if choices else {}
    text = (msg_obj.get("content") or "").strip()
    finish = choices[0].get("finish_reason") if choices else None
    usage = d.get("usage") or {}
    return CallResult(
        ok=bool(text),
        text=text,
        model_requested=model,
        # Deliberately None. Providers echo dated snapshots (gpt-5 ->
        # gpt-5-2026-01-15) that don't fit the Anthropic alias/-YYYYMMDD shape
        # the served-guard tolerates, and a false mismatch would discard a good
        # answer. The echoed id goes in provider_model for provenance — NOT in
        # served_all, whose non-None value means "multiple models reported" and
        # is read as contamination evidence by analyze._classify_served_mismatch.
        model_served=None,
        served_all=None,
        provider_model=d.get("model"),
        effort=effort,
        input_tokens=int(usage.get("prompt_tokens", 0) or 0),
        output_tokens=int(usage.get("completion_tokens", 0) or 0),
        stop_reason=finish,
        error=None if text else f"empty result (stop_reason={finish})",
        backend="openai_compat",
        raw=d,
    )


_BACKENDS: dict[str, Callable[..., CallResult]] = {
    "claude_cli": _call_cli,
    "anthropic_api": _call_api,
    "ollama": _call_ollama,
    "openai_compat": _call_openai_compat,
}

# Error markers that will not heal on retry — fail fast instead of burning
# max_retries x timeout on them. Deliberately specific: a generic substring
# like "not found" could misclassify a transient error ("session not found")
# as permanent. Timeouts / 429s / 5xx never match these.
_PERMANENT_ERROR_MARKERS = (
    "claude cli not found",  # our canonical FileNotFoundError message
    "served_mismatch",       # deterministic while a fallback/repoint persists
    "model not found", "unknown model", "invalid model",
    "unknown option", "unrecognized option",
    "invalid_request", "not_found_error",
    "authentication", "permission", "billing",
    "try pulling",             # ollama: model not in the local library
    "does not support think",  # ollama: think sent to a non-thinking model
    # openai_compat: config-class HTTP codes (bad key, unknown model, rejected
    # param). 429 and 5xx are deliberately absent so they stay transient.
    "openai http 400", "openai http 401", "openai http 403", "openai http 404",
)


def _is_permanent_error(err) -> bool:
    return isinstance(err, str) and any(m in err.lower()
                                        for m in _PERMANENT_ERROR_MARKERS)


_DATED_SUFFIX = re.compile(r"-\d{8}$")


def _served_matches(requested: str, served: Optional[str]) -> bool:
    """True unless the serving model is genuinely different.

    Tolerates ONLY alias<->dated-snapshot resolution (claude-opus-4-8 vs
    claude-opus-4-8-YYYYMMDD, either direction). Any other suffix variant —
    a '-fast' tier, a different generation sharing a prefix — counts as a
    mismatch: those are exactly the silent fallbacks this guard exists for.
    """
    if not served:
        return True  # unknown, not provably mismatched
    if served == requested:
        return True
    if served.startswith(requested) and _DATED_SUFFIX.fullmatch(served[len(requested):]):
        return True  # requested the alias, served the dated snapshot
    if requested.startswith(served) and _DATED_SUFFIX.fullmatch(requested[len(served):]):
        return True  # requested the dated snapshot, served reports the alias
    return False


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #


class Runner:
    def __init__(self, cfg: dict, cache_dir: str | Path = "cache"):
        rc = cfg["runner"]
        self.backend = rc.get("backend", "claude_cli")
        self.max_retries = int(rc.get("max_retries", 4))
        self.backoff = float(rc.get("retry_backoff_seconds", 5))
        self.timeout = int(rc.get("timeout_seconds", 240))
        self.max_parallel = int(rc.get("max_parallel", 8))
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._fn = _BACKENDS[self.backend]
        self._opts = {
            "tools": rc.get("tools", ""),
            "no_session_persistence": bool(rc.get("no_session_persistence", True)),
            # ollama backend knobs (ignored by the other backends)
            "ollama_host": rc.get("ollama_host", "http://localhost:11434"),
            "ollama_num_predict": int(rc.get("ollama_num_predict", 4096)),
            "ollama_num_ctx": int(rc.get("ollama_num_ctx", 8192)),
            # openai_compat backend knobs (ignored by the other backends)
            "openai_base_url": rc.get("openai_base_url", "https://api.openai.com/v1"),
            "openai_api_key_env": rc.get("openai_api_key_env", "OPENAI_API_KEY"),
            "openai_extra_body": rc.get("openai_extra_body") or {},
            "openai_map_effort": bool(rc.get("openai_map_effort", False)),
        }
        self._lock = threading.Lock()
        self._spend = 0.0
        self._calls = 0

    # -- single call with cache + retry ------------------------------------ #
    def call(self, model: str, system: str, prompt: str, effort: str,
             run_index: int = 0, use_cache: bool = True,
             backend: Optional[str] = None) -> CallResult:
        # Per-call backend override (cohort entries may pin one, e.g. local
        # open-weights models via ollama). The effective backend is part of
        # the cache key, so entries never cross backends.
        be = backend or self.backend
        fn = _BACKENDS[be]
        key = _cache_key(be, model, system, prompt, effort, run_index)
        cpath = self.cache_dir / f"{key}.json"
        if use_cache and cpath.exists():
            try:
                d = json.loads(cpath.read_text())
                # Reject entries served by the wrong model (silent-fallback
                # artifacts cached before this guard existed) so resumes
                # re-run them instead of laundering the contamination.
                if d.get("ok") and _served_matches(d.get("model_requested") or model,
                                                   d.get("model_served")):
                    r = CallResult(**{k: v for k, v in d.items()
                                      if k in CallResult.__dataclass_fields__})
                    r.cache_hit = True
                    return r
            except Exception:
                pass  # corrupt cache entry — recompute

        last: Optional[CallResult] = None
        for attempt in range(1, self.max_retries + 1):
            r = fn(model, system, prompt, effort, self.timeout, self._opts)
            r.attempts = attempt
            r.called_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            with self._lock:
                self._spend += r.cost_usd  # every attempt costs real money
            if r.ok and not _served_matches(model, r.model_served):
                r.ok = False
                r.error = f"served_mismatch: requested {model}, served {r.model_served}"
            last = r
            if r.ok:
                break
            if _is_permanent_error(r.error):
                break  # retrying won't help; don't burn quota on it
            if attempt < self.max_retries:
                time.sleep(self.backoff * attempt)

        assert last is not None
        with self._lock:
            self._calls += 1
        if last.ok and use_cache:
            cpath.write_text(json.dumps(last.to_json(), ensure_ascii=False))
        return last

    # -- batch with bounded parallelism ------------------------------------ #
    def map(self, jobs: list[dict],
            on_done: Optional[Callable[[int, dict, CallResult], None]] = None
            ) -> list[CallResult]:
        """Each job dict: {model, system, prompt, effort, run_index[, backend]}."""
        results: list[Optional[CallResult]] = [None] * len(jobs)
        with cf.ThreadPoolExecutor(max_workers=self.max_parallel) as ex:
            fut_to_i = {
                ex.submit(self.call, j["model"], j["system"], j["prompt"],
                          j["effort"], j.get("run_index", 0),
                          backend=j.get("backend")): i
                for i, j in enumerate(jobs)
            }
            for fut in cf.as_completed(fut_to_i):
                i = fut_to_i[fut]
                r = fut.result()
                results[i] = r
                if on_done:
                    on_done(i, jobs[i], r)
        return results  # type: ignore

    @property
    def total_spend_usd(self) -> float:
        return self._spend

    @property
    def n_live_calls(self) -> int:
        return self._calls


if __name__ == "__main__":  # ad-hoc smoke test
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-haiku-4-5-20251001")
    ap.add_argument("--prompt", default="What is 7+5? Reply with only the number.")
    ap.add_argument("--effort", default="low")
    args = ap.parse_args()
    cfg = {"runner": {"backend": "claude_cli", "max_parallel": 1}}
    r = Runner(cfg, cache_dir="cache").call(
        args.model,
        "You are answering a knowledge assessment. Follow instructions exactly.",
        args.prompt, args.effort)
    print(json.dumps(r.to_json(), indent=2))
