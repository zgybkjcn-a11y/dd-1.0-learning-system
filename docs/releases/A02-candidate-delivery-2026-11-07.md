# A02 候选源码交付单

2026-11-07。状态：**已整理，待提交**。基线为 `main` / `deef3199f558ba72bbe3f2ff0c704586674a2232`；以下两组的提交 SHA 均为 `null`，没有推送或部署。逐文件路径、来源和指纹见[机器清单](A02-candidate-files-2026-11-07.json)，验收见[A02 记录](../verification/A02-candidate-delivery-2026-11-07.md)。

## 审阅和提交顺序

| 单元 | 文件数 | 内容与依赖 | 交付状态 |
| --- | --- | --- | --- |
| U1 证据候选与可移植测试 | 24 | 页级服务、六方法 Tool、原生探针、离线片段脚本及合成测试、锁文件、测试隔离与 workflow；基于上述 HEAD | 已整理，待提交 |
| U2 说明、计划与交付记录 | 22 | 测试说明、证据报告、入口、25 项计划/台账、A01/A03/A02 记录；依赖 U1 | 已整理，待提交 |

U1 内可按以下主题审阅，但作为一个原子提交单元：`page_evidence` 被数学参考、Tool 以及离线片段脚本共同使用；页级测试又依赖 A03 的根合成夹具。只提交旧页级文件或先提交片段脚本会得到不完整版本。U2 集中处理相互链接的文档，避免拆分出缺少计划、测试说明或报告的入口。两组全部应用后才是本次完整交付候选。

### U1 明确文件清单

```text
.github/workflows/tests.yml
conftest.py
deploy/open-webui-reuse/readonly_study_tools.py
learning_service/math_references.py
learning_service/study_support.py
learning_service/textbooks.py
pytest.ini
requirements-dev.lock
requirements-dev.txt
scripts/probe_readonly_study_native.py
scripts/textbook_passage_sample.py
tests/test_family_adventure_browser.py
tests/test_family_practice_browser.py
tests/test_local_textbook_materials.py
tests/test_main_study_bridge.py
tests/test_manual_objective_browser.py
tests/test_math_references.py
tests/test_readonly_study_tools.py
tests/test_study_support.py
tests/test_study_support_browser.py
tests/test_study_workbench_browser.py
tests/test_textbook_passage_sample.py
tests/test_textbooks.py
tests/test_variant_review.py
```

### U2 明确文件清单

```text
README.md
docs/PROJECT-REVIEW-2026-11-07.md
docs/README.md
docs/TESTING.md
docs/open-webui-reuse/README.md
docs/open-webui-reuse/main-chat-tools.md
docs/open-webui-reuse/textbook-evidence-chain.md
docs/plans/DD-1.0-NEXT-IMPLEMENTATION-2026-11-07.md
docs/plans/DD-1.0-WORK-PLAN-2026-11-07.md
docs/plans/RESUME-NEXT-WORK.txt
docs/plans/dd-next-work-tracker.json
docs/releases/A02-candidate-delivery-2026-11-07.md
docs/releases/A02-candidate-files-2026-11-07.json
docs/releases/A02-local-material-backup-2026-11-07.md
docs/releases/README.md
docs/releases/current-manifest.json
docs/releases/current-state.md
docs/verification/A01-current-state-2026-11-07.md
docs/verification/A02-candidate-delivery-2026-11-07.md
docs/verification/A03-portable-tests-2026-11-07.md
docs/verification/textbook-evidence-2026-11-07.md
docs/verification/textbook-passages-2026-11-07.md
```

## 测试与源码对应

A02 没有修改 U1。当前 144 个可移植测试输入文件与 A03 最终源码清单、浏览器测试源码清单逐一相同；沿用 **503 单元/契约、12 浏览器通过，失败/错误/跳过均为 0**。本批只执行文件、补丁及交付一致性检查，没有重复整套测试。

A03 单元组 `unit-r3` 与最终版本只差 `conftest.py::launch_browser` 中增加默认 `channel="chromium"`。A02 用历史 SHA256 精确还原当时文件并比较 AST，其他节点一致；该夹具只在被单元组排除的六个浏览器模块使用，最终浏览器组及版本故障控制已覆盖变更。详细对应关系在本批 `source-evidence-verification.json`。不能把两次运行误写成所有文件完全相同的一次全量测试。

历史 117 项/原生六方法结果属于页级候选；最终源码与探针未变。29 项片段合成测试已包含在上述 503 项中；20 个实际片段开发问句仍不是独立盲测。实物教材测试和 GitHub 远端 CI 未运行，家长设备与真实模型验收没有新增结论。

## 可审阅本地包

独立证据目录：`learning_data/verification/a02-candidate-delivery-20261107T095108Z/`。

- `workspace-before.json`、`files-before/`：A02 前 42 个脏文件的状态、哈希和副本；保留原有改动。
- `review-packet/01-code-tests.patch`、`02-documents.patch`：按以上顺序应用到指定 HEAD 的两份补丁，包含未跟踪文件。
- `review-packet/files/`、`MANIFEST.json`：46 个显式允许文件的审阅副本与完整哈希；机器清单自身的哈希由外层 manifest 记录，避免自引用。
- `patch-replay/`：在独立临时 Git 目录按顺序应用补丁后的校验副本，没有 commit；144 个测试输入与当前候选一致。它不是运行服务目录。
- `delivery-validation.json`：补丁还原、文件覆盖、依赖、链接、私有材料边界、HEAD/index 与原改动保护检查。

这些是本机审阅材料，没有生成新的运行镜像或可直接部署的封包。不使用历史 `prepare_learning_release.py` 的旧白名单来冒充本轮完整候选。

## 已有提交、材料与后续操作

三个静态样本的 9 个资产已在 `deef3199` 中，工作树与候选快照哈希一致，**不属于 U1/U2 新增代码**。它们仍未上线，沿 A09 独立推进。U1 中的主站浏览器测试修改属于测试可移植性，不是重新实现三个样本。

教材 PDF、原图、正文片段、预览、数据库和环境秘密不进入两组源码或审阅包。现有教材材料和历史证据的保存要求见[本地材料备份说明](A02-local-material-backup-2026-11-07.md)。检查未发现私有教材长引文或真实凭据混入候选；该检查不替代未来新增文件的审阅。

以后收到适用提交指令时：先核对 HEAD、工作区及本清单哈希是否变化；有新增 A04 等工作则另成增量或更新交付清单，不能机械提交整个脏目录。按 U1/U2 明确路径暂存，审阅 staged diff 后才提交，登记实际 SHA；推送与部署分别记录。当前 Git index 保持原样。

本批本地回退仅对照 `files-before/` 撤销 A02 的九份文档更新和四份新增文档，先确认没有后续编辑；不回退 U1 或 A01/A03，不执行整树 reset/checkout/clean。线上回退仍按[当前兼容清单](current-state.md)，候选 Tool 1.1.0 不可单独安装到当前旧后端。

下一项 **A04：细分会话与 Tool 失败**。A02 提交仍待指令，但本地依赖已就绪，不阻塞 A04。
