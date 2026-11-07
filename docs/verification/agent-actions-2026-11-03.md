# Agent 动作与诊断 worker 回归证据

日期：2026-11-03（Asia/Shanghai）

## 验证范围

本轮清除了 Agent 动作执行层的占位返回，并验证动作仍受学习者范围、步骤预算和可信交互边界约束：

- `get_mistakes`、`get_progress`、`get_attempt` 使用当前学习者范围执行持久化读取。
- `request_document_analysis` 校验批次归属和状态，写入 `document_analysis` job；worker 处理后保留 `needs_review` 候选。
- `request_diagnosis` 校验错题归属，写入 `diagnosis` job；诊断 provider 调用前后均重新校验 lease，结果写入 `diagnoses` 并保持 `needs_review`。
- `request_variant` 写入受审核门槛约束的 `variant_generation` job。
- `request_hint` 写入辅助暴露事件并标记测验题项，`request_visual` 只使用已审核数轴模板；这些动作不获得最终确认、判分或改阶段权限。
- Agent action 本身只返回 `requires_trusted_ui` UI-only handoff，不创建 challenge、不返回 nonce、不消费确认或答案提交；薄 Tools 适配器的原生 `input`/`confirmation` 回调由隔离注册报告另行验证。

## 自动化命令与结果

```text
pytest -q tests/test_learning_service.py -k 'agent_ or diagnosis_worker'
6 passed, 47 deselected

pytest -q
62 passed（本报告生成时的全量快照；之后全量回归曾为 76/77/78 passed，当前为 91 passed）

python3 -m compileall -q learning_service tests
passed
```

覆盖的新增测试包括：

- `test_agent_document_analysis_action_queues_scoped_batch_and_worker`
- `test_diagnosis_worker_does_not_persist_after_lease_is_stolen`
- `test_agent_actions_execute_scoped_reads_and_durable_requests`
- `test_agent_hint_and_attempt_actions_preserve_service_boundaries`

## 边界

测试使用隔离临时 SQLite、合成图片和确定性 provider。它证明服务端状态机和权限边界，不证明真实 Open WebUI Tools 注册/回调、真实 OCR/模型质量或真实学生资料外发。诊断和变式输出仍是待复核候选，不能直接批准或晋阶。
