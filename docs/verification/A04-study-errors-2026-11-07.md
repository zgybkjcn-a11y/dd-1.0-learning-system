# A04 会话、网关与 Tool 失败分类验证

2026-11-07（Asia/Shanghai）。本地工程验收通过，未提交/部署。现在能区分学习会话过期、真正身份冲突、档案 revision 变化、教材缺失、检索超时和上游故障；每类给出可执行恢复方式和脱敏请求编号。未知故障明确暂不可用，不能据此自动重绑或切档。操作与完整分类见[故障排查表](../open-webui-reuse/study-error-recovery.md)。

## 输入与实现

输入为 `main` / `deef3199f558ba72bbe3f2ff0c704586674a2232` 和 A02 固定的未提交候选。A02 的[46 文件交付单](../releases/A02-candidate-delivery-2026-11-07.md)与本地审阅包保持历史快照；以下改动作为 A04 增量单独记录，不能将旧清单当作当前文件的哈希。

| 文件 | 本批增量 |
| --- | --- |
| `learning_service/browser_auth.py` | 只对仍绑定且未撤销的已知会话返回过期码；未知/撤销会话继续拒绝，未新增绑定或会话写入 |
| `learning_service/login_gateway.py` | 先检查会话上游状态和格式，再判定真实身份不符；细分认证/服务/检索超时，允许清单内错误重新构造，随机请求 ID 与固定字段日志 |
| `deploy/open-webui-reuse/readonly_study_tools.py` | 候选版本 **1.1.1**；有限错误码、恢复提示、请求编号和重试标记；丢弃原始错误消息/详情，保留前后身份/档案和引用校验 |
| `tests/test_study_errors.py` | 新增 49 个合成用例：过期与撤销、真实冲突、故障分类、请求编号防伪、上游消息/异常脱敏、证据丢弃、传输/回调失败 |
| `tests/test_login_gateway.py`、`tests/test_readonly_study_tools.py`、`tests/test_textbooks.py` | 夹具改用真实错误解码入口，旧预期精确区分 504 超时及 502 格式错误；保留原隔离/引用用例 |

Tool SHA256：`8cf5a018f2011872baf4bc3c3b05981631725456ee893c6489cf502f9669b7a9`。旧 1.1.0 候选保存在 A02 本地包，历史注册 1.0.0 不变。六个公开方法签名及原生 citation 成功路径保持。

## 实际验证

证据目录：`learning_data/verification/a04-study-errors-20261107T101647Z/`。开始时保存 46 个既有脏文件与本批额外涉及源码的指纹、副本；测试在新的 145 文件允许列表副本中运行，没有教材、运行数据库或环境秘密。复用 A03 已按哈希锁安装的 Python 3.12.12 venv，不冒称本轮重新安装了依赖。

| 验证 | 结果 |
| --- | --- |
| 首轮定向组 | **131 passed**，70.72 秒；新增故障组与网关、会话、只读 Tool、教材原用例 |
| 最终单元/契约组 | collected 566、selected **552 passed**、14 deselected，**0 failed / 0 errors / 0 skipped**，143.07 秒；包含新增 49 项 |
| 固定 WebUI 0.12.5 原生加载 | **通过**：Tool 1.1.1、六方法、2 条引用、宿主保留参数隐藏；当前 Tool 哈希匹配；152.77 秒，退出码 0 |
| 浏览器/实物/远端 CI | 本批均未运行；A03 的 12 项浏览器结果只保留历史，不写为当前源码重新验证 |

最终测试命令在本批 `clean-source/` 执行：

```bash
../../a03-portable-tests-20261107T091348Z/venv/bin/python -m pytest tests -q \
  -m 'not browser and not local_materials' --junitxml=../unit-r2.xml
```

`source-manifest-r1.json` / `source-manifest-r2.json` 固定两轮输入，最终 145 文件与工作区一致。两轮没有测试失败；最终补充请求编号防伪及缺会话恢复用例后进入全单元组。原 Starlette/httpx TestClient 弃用提示仍有 1 条，不影响结果。

原生验证使用固定镜像 `sha256:0b399a8ba34558e181d316750455f2a95376a38cd60a61b9c942e138898944bd`，`--network none --read-only`、临时数据目录、离线开关，仅只读挂载 Tool 和原有探针两个文件。首轮缺少 `/app/backend` 导入路径而退出 1，尚未加载 Tool；修正容器工作目录/PYTHONPATH 后通过。45 秒时探针输出导入耗时诊断，随后正常完成。命令、首轮失败及后续日志均保留，临时容器已自动移除；没有挂载正式 data。

## 证据与验收边界

`test-summary.json`、两组 JUnit/日志和 `native-tools.json` 分别记录源码与结果。`delivery-validation.json` 核对当前文件、历史包保护、状态与链接；`a04-increment.patch` 和 `increment-manifest.json` 保存相对 A04 起点的代码/文档增量，便于审阅和精确回退。

应用新增日志只含随机请求 ID、允许分类码及 HTTP 状态；合成标记验证 Cookie、账号/学习者、上游错误正文、答案及原始异常均不进入错误结果或新增日志。请求编号不是认证凭据，也不是分布式追踪。正常有资料仍按原引用投影，正常空结果不与服务故障混同。回调失败前若宿主已收到部分引用，本批未实现宿主撤回协议。

本批没有更改前端界面、学习记录、账号绑定或实际教材；未调用真实生成、embedding、外部 OCR，未写生产向量/Goal，未提交、推送或部署，也未发送消息。当前运行事实仍沿用 A01 的时间快照，正式 Tool 未回读。上游配置、服务运行和真实家庭体验的验收没有因此提升。

回退只对照本批 `files-before/` 撤销 A04 增量，保留此前页级候选、A03 测试基础及 A02 文档，不整树 reset/checkout/clean。已更新[台账](../plans/dd-next-work-tracker.json)与[当前清单](../releases/current-state.md)。下一项 **A06：冻结独立检索与引用评测**，随后 A05；三个静态样本仍可按 A09 独立推进。
