# 教材证据链第一阶段验证

日期：2026-11-07。基线提交 `deef3199f558ba72bbe3f2ff0c704586674a2232`。本轮从干净工作区继续用户“先借鉴 RAGFlow 的证据链设计”的指令，完成本地候选；未提交、推送或部署本轮改动。

设计与上游固定版本/许可见 [教材证据链](../open-webui-reuse/textbook-evidence-chain.md)。本轮新增页级身份和证据类型，尚未建立已核验原文片段库或逐句回答核验器。

## 变更

- 教材检索/浏览响应增加 `evidence`，由本地目录生成来源、版本、PDF 哈希、实际章节、书内页码、物理页码及稳定 ID。显式冲突的索引 PDF 哈希被过滤。
- 数学概念原页复用同一页级证据；数学学科助手透传本地参考文件哈希，使同一概念在不同入口具有一致的讲解身份。
- 六方法 Tool 候选升至 **1.1.0**，投影允许的证据字段并检查一致性，原生 citation 附带对应身份；检索明确返回 `locations_only` 或 `no_evidence`。
- 未核验文字仍不进入 Tool 或 citation；页级定位和本地讲解都没有因此获得教材原句或判分资格。

候选 Tool SHA256：`34442c897e0fd98aebe9264f035704a1bbd3ad90351ea2e2f60ed0575bace778`。线上原注册版本仍为 1.0.0，SHA256 `733ad01dc38ed6b09fcae69047ff731e0eb83d59b0a2dd2432595a3508c6a650`；本轮没有读取正式 Tool 数据库进行复查或更新。

## 验证结果

证据目录：`learning_data/verification/textbook-evidence-20261107/`，处于既有忽略目录中，不加入源码提交。

| 验证 | 结果与实际覆盖 |
| --- | --- |
| `tests/test_textbooks.py`、`tests/test_math_references.py`、`tests/test_study_support.py`、`tests/test_readonly_study_tools.py` | **117 passed in 54.40s**；合成账号/数据库/检索，部分既有数学测试读取公开本地教材 PDF |
| 身份与范围 | 排序、重复分块、不同提取文字、整册/章内查询保持同页身份；PDF 变化产生新身份；原有年级、版别、书章和页码边界继续通过 |
| 内容与引用 | 搜索和概念查询的同页身份一致；本地讲解拥有单独身份；Tool JSON 与 citation 的 ID、哈希、双页码、URL 对应一致 |
| 失效行为 | 无合格页不发 citation；修改 ID、哈希、页码、书章或审核资格会拒绝；额外未审核文字/外部链接不投影；档案 revision 在查询中变化则丢弃结果 |
| 原生 WebUI 0.12.5 | 固定镜像中的 `load_tool_module_by_id` / `get_tools` 成功加载六方法，宿主保留参数对模型隐藏，概念与检索生成 **2 条**带证据身份的 citation |
| 检查 | `git diff --check` 通过；已通过且未改动的完整浏览器流程未重复运行 |

测试命令：

```bash
python -m pytest -q tests/test_textbooks.py tests/test_math_references.py tests/test_study_support.py tests/test_readonly_study_tools.py
```

原生探针使用 `scripts/probe_readonly_study_native.py` 和固定镜像 `sha256:0b399a8ba34558e181d316750455f2a95376a38cd60a61b9c942e138898944bd`，设置 `--network none --read-only --tmpfs /tmp`，`DATA_DIR=/tmp/dd-chat-native`、`OFFLINE_MODE=true`，关闭模型自动更新与远程模型接口。仅以只读方式挂载候选 Tool 和探针两个源码文件，未挂正式 data；运行结束自动移除临时容器。初始化超过 45 秒时探针留下导入栈诊断，随后正常完成并输出 `passed=true`，进程退出 0。

保留的证据：

- `pytest.log`：117 项测试结果。
- `native-tools.log`、`native-tools.json`：原生加载日志与结构化结果；真实模型调用 0、断网、正式数据挂载 false。
- `sample-outputs.json`：一个合成页命中和一个空命中的 Tool JSON/citation，可直接检查证据结构；不是内容相关性测评或真实问答。
- `source-manifest.json`：四个运行时源码、两个测试文件及原生探针的 SHA256。

## 当前限制与继续位置

本轮只验证契约、过滤和引用事件，没有发送真实检索 embedding 或生成请求，没有验证模型正文引用质量、召回准确率或教学效果。哈希绑定与引用卡不能证明某项回答正确。

正式运行状态只读核对：当前 Compose 的四个家庭服务均运行，家庭 API healthy；主站对应 Open WebUI 容器 healthy。Goal 只读结果为空，未写入。部署、绑定、私有 Tool 注册、学习记录、教材索引及数据卷均未改变。

候选 Tool 1.1.0 需要本轮网关/服务端字段；旧 Tool 1.0.0 可以忽略新增字段继续工作。不得单独替换线上 Tool，不得用现有注册脚本重复注册或绕过来源哈希检查。

下一阶段先按设计文档建立限定片段的转写复核和独立内容复核，再做 5–10 页、15–20 问的小样本。此阶段尚未实施；二下数学完整页双重审核通过数保持为 0。之前的等式演示、可视化知识路线及复习 PDF 小样本已经在基线中提交并推送，但仍未部署，本轮未改变该状态。
