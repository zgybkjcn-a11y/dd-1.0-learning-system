# 错题导入内容持久化回归（2026-11-04）

本次回归补齐图片、PDF、DOCX、XLSX 的导入确认后错题本列表/详情链路，并核对 `mistake_entries.content_json`。测试使用合成资料和默认 deterministic mock provider；不代表真实 OCR、真实学生资料或真实 provider 验收。

## 覆盖范围

参数化测试：`tests/test_learning_service.py::test_uploaded_mistake_confirmation_persists_content_judgment_source_and_review_card`

四个格式均执行以下流程：

1. 上传资料并创建导入批次。
2. 请求分析，运行本地 worker，读取待复核候选。
3. 以合成的人工作判定写入题干、学生作答、`incorrect` 判定、教师证据和知识目标。
4. 获取并提交一次性可信确认。
5. 读取错题本列表和详情，并对账数据库中的 `mistake_entries.content_json`、`import_judgments.evidence_json` 和复习卡。

## 结果

- PNG、PDF、DOCX、XLSX：`4 passed`。
- 列表和详情均保留题干 `5 × 6，求积。`、学生作答 `35`、判定 `incorrect` 和教师证据。
- `mistake_sources` 返回 `uploaded_work`、原候选 ID、判定和证据；详情返回对应 active 复习卡。
- 数据库直接读取的 `mistake_entries.content_json` 与列表内容一致；人工 judgment 证据解析后与确认时对象一致。
- 该回归暴露并修复了确认路径创建错题条目时未写入 `content_json` 的缺口。

## 验证命令

```text
pytest -q tests/test_learning_service.py -k uploaded_mistake_confirmation_persists_content_judgment_source_and_review_card
4 passed, 72 deselected

pytest -q
101 passed in 18.86s

python3 -m compileall -q learning_service tests scripts
git diff --check
python3 scripts/verify_goal_consistency.py
tasks=26, evidence paths=144, backlog task rows=26, QA matrix rows=17, manifest path references=22, release authorization boundaries intact
```

全量与静态检查仍是本地确定性证据。腾讯 OCR 默认 mock、`TENCENT_OCR_EXTERNAL_CALLS_ENABLED=0`，没有真实 API 调用、真实资料外发或生产部署；Goal 仍不可标记为 complete。
