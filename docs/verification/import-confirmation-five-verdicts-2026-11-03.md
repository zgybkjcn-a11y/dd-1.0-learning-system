# 整卷候选五类判定与错题来源边界

日期：2026-11-03（Asia/Shanghai）

本证据只覆盖独立 SQLite 中的合成候选与人工 judgment，不表示 OCR、学科标注或真实整卷质量通过。

## 验证

最新全量回归 `pytest -q`：78 passed（`test_learning_service.py` 64、`test_learning_tools.py` 11、`test_open_webui_compat.py` 3）。其中 `test_import_confirmation_accepts_all_five_manual_verdicts_but_only_records_mistakes` 已在全量运行中通过。

该测试为 `correct`、`incorrect`、`partial`、`unanswered`、`undetermined` 各建立一条当前 revision 的候选、非空证据和匹配的人工 judgment，逐条生成可信 challenge 并确认。五类候选都成为已确认记录；只有 `incorrect` 和 `partial` 创建错题来源，其余三类不会创建错题来源。

`test_import_confirmation_requires_unique_current_manual_judgments` 覆盖自动判定候选、空证据、缺失/不一致的人工 judgment、重复候选 ID 和非法 revision；这些输入在 challenge 阶段被拒绝。相关服务实现和持久化断言位于 `tests/test_learning_service.py`，候选状态与 judgment 校验位于 `learning_service/app.py`。

本次续跑复验 `pytest -q tests/test_learning_tools.py tests/test_open_webui_compat.py`：14 passed（Tools 11、Open WebUI compatibility 3）。五类判定专用服务测试由最新 `pytest -q` 全量结果 78 passed 覆盖；可信 UI timeout regression 证据见 `trusted-ui-timeout-2026-11-03.md`。

## 验收边界

结果证明的是服务端判定枚举、人工证据门槛和错题来源映射的确定性状态机。测试没有提供真实学生卷面、人工参考答案集、OCR/模型质量测量或学科人工裁决；这些项目仍按 `docs/goal/BLOCKERS.md` 阻塞记录。
