# Trusted UI callback timeout verification

Date: 2026-11-03 (Asia/Shanghai)
Scope: Open WebUI Tools adapter timeout behavior with synthetic callback and service responses; no real provider, learner data, or production Open WebUI was used.

## Change

`learning_service/tools.py` now applies the same 120-second ceiling to asynchronous `__event_call__` waiting that it advertises in the native `input` and `confirmation` event. If the host callback does not return before the limit, the adapter returns `TRUSTED_UI_NOT_CONFIRMED` and does not request or submit a challenge. Synchronous callback errors and non-affirmative callback values retain the existing fail-closed behavior.

The regression shortens the limit to 1 ms and holds the asynchronous callback open. It covers both `confirm_import` and `submit_answer`, checks that the event advertises the configured timeout, and asserts that neither confirmation nor answer challenge/submission endpoints are called.

## Verification

```text
pytest -q tests/test_learning_tools.py tests/test_open_webui_compat.py
14 passed

pytest -q
78 passed in 15.58s (64 learning service + 11 Tools adapter + 3 Open WebUI compatibility)
```

This is deterministic adapter evidence. It does not replace a real Open WebUI browser WebSocket callback or model-initiated tool call, which remain pending in `docs/goal/BLOCKERS.md`.
