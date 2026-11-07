# 学习服务、数学参考与学科阅读 Tools 验证

后续最新：含“理解工坊”工作台入口的新镜像已上线，见[工作台验证与当前部署](study-workbench-2026-11-06.md)。下文source-v1/候选镜像与“未部署”描述保留本阶段历史；正式WebUI Tools注册仍未执行。

2026-11-06，工作目录 `/home/deniskorfei/projects/open-webui`。适配器 1.2.0；目标 Open WebUI 0.12.5；schema 11，无迁移。用户要求通过现有学习服务与 Tools 接入，并新增参考 faststudy 的 SCENARIOS 场景，帮助各学科学习理解。

## 完成的实现

- `learning_service/math_references.py` 与 `GET /api/v1/math-references`：冻结的20题/18概念映射、当前/更早章原页、最多两层/六个先修参考、题目级同章最多三道相关题编号。
- `learning_service/study_support.py` 与 `GET /api/v1/study-support`：当前年级可用学科的本地阅读问题串、Mermaid 图和 Marp Markdown 学习卡。数学沿用冻结映射；其他学科明确 `reading_scaffold_only`。
- `learning_service/tools.py` 新增 `get_math_scope`、`get_math_question_reference`、`get_math_concept_reference`、`get_study_support`，共15个公开方法。所有新增查询先后核对宿主身份与共享学习者版本，接口自身也拒绝查询期间切换。
- 网关 GET 白名单、OpenAPI 两个新路径、学习教练草稿、来源/许可证和新源码候选 profile 已补齐。旧 practice/textbook/runtime/schema 候选继续可验证。
- 独立离线理解样例覆盖当前13册/111个整书或章节范围，包含乘法/两种除法和有理数数轴参数演示、七门学科阅读方法、Markdown/图导出。

数学参考 JSON SHA256：`b9f483f264d9be9124e1f682a9736e37010a5d78919510eaf47de604c916c9ba`。
适配器 SHA256：`bfd099c4066476704327a852953e847f0faa1816781843dfd6a180f9f71d3b32`。
最终离线 HTML SHA256：`2c64c00ea011aaf6c8420b5f004de35a2afa95daecd464ec8f518f67c2248539`。

## 测试结果

115项服务/Tools/兼容/网关/共享上下文/打包测试通过：

```bash
python3 -m pytest -q tests/test_math_references.py tests/test_study_support.py \
  tests/test_reuse_tools.py tests/test_open_webui_compat.py tests/test_learning_release.py \
  tests/test_login_gateway.py tests/test_learner_context.py --tb=short
```

关键覆盖：章节可选、跨年级/跨书/跨章拒绝、无映射不回退、未来页隐藏、division并列和解方程依赖等式性质、题干/键/单位/validator/版本变化失效、参考/PDF/题库校验失败、只读查询、无学生材料读取、查询参数注入、宿主身份、切换离开再回来也丢弃结果、嵌套未知字段裁剪、输出长度、七学科适用性、非数学不输出未审核答案、旧候选验证。

2项浏览器测试通过，宽度390/1280：同组乘除演示独立核算、减去负数的数轴方向、学科/章节切换、第五章等式性质核对点、下载的 Markdown 文件、0页面错误/0网络请求/0横向溢出。

```bash
DD_STUDY_EXAMPLES_DIR=/home/deniskorfei/projects/open-webui/learning_data/verification/scenarios-integration-20261106/examples-v2 \
  python3 -m pytest -q tests/test_study_support_browser.py --tb=short --maxfail=1
```

浏览器需要本机 Chrome 的沙箱外运行授权；使用已批准的受限测试命令，页面通过 `set_content` 装入，未打开真实学习入口。证据：`examples-v2/browser-390.json`、`browser-1280.json` 及同名尺寸 PNG。

## 原生 Open WebUI 验证

在已有镜像 `sha256:0b399a8ba34558e181d316750455f2a95376a38cd60a61b9c942e138898944bd` 的一次性容器中调用真实 `load_tool_module_by_id` / `get_tool_specs` / `get_tools`。容器 `--network none --read-only`，只有 `/tmp` 和默认 data 路径为临时内存目录；仅只读挂载候选源码、合成家庭创建脚本和两册公开PDF，**未挂载正式 WebUI data**。

原生加载15方法、Valves、隐藏保留参数、宿主subject、两个档案切换、四个新增方法及七门学科调用通过。数据库工具/用户/组查询用合成内存对象替代；业务请求送到本机 TestClient 的全新学习库。无真实注册账号、真实模型调用或正式 Tool 记录写入。Python脚本为 `scripts/probe_math_reference_native.py`，结构化结果为 `learning_data/verification/math-reference-tools-20261106/native-loader.json`。

## 离线镜像及部署候选

68个白名单源码文件已从新source候选离线、无缓存构建，依赖来自现有本机wheel与已核查的Python OCI导出，无网络下载。source set：`35f3f87d8c2d854b5867a0f2eb7d6628d2a1c313e83c236e80efb0c227f9d7d9`。新镜像：`sha256:8312a177fb93ee27dcf91b84b757f59f6bf027d7f7b7fdf30c072ac79b731731`，本机tag `dd-learning:reuse-study-support-20261106`，未推送或部署。

新镜像在断网/只读的一次性容器中启动实际uvicorn服务，通过标准库HTTP调用验证四个新增Tools、两档案和七科。仅挂载临时合成数据目录与两册公开PDF，无正式WebUI/家庭数据；provider0。结果在 `learning_data/verification/math-reference-tools-20261106/candidate-runtime.log`，脚本 `scripts/probe_study_candidate.py` 不需要测试依赖。

候选Compose：`learning_data/deployments/family-math-20261105/compose-study-support-20261106-candidate.json`。由当前四题部署JSON生成，逐字段比较确认只替换API/worker/gateway三个镜像；卷、secret引用、网络、proxy和其他环境配置完全相同。`docker compose --env-file /dev/null ... config --quiet`通过；未执行up。source manifest保留源码封装时的固定状态，镜像构建证据另存在 `build/build.json`。

## 来源与限制

固定 SCENARIOS commit 及三个重点项目的 README/真实 LICENSE 均保存在 `learning_data/verification/scenarios-integration-20261106/`。EduLab Apache-2.0，DeepTutor Apache-2.0，OpenMAIC MIT。本轮采用展示设计和导出格式，本地编写代码；没有安装这些平台、执行上游生成器、复制出版社正文或写入生产向量。具体采用见[SCENARIOS记录](../open-webui-reuse/scenarios-adoption.md)。

`reference_only=true`，`eligible_as_grading_basis=false`，`teacher_reviewed=false`，`mastery_claim=null`。全教材页双重审核仍未完成；二下未审核OCR不加入出题/判分。没有创建题目、修改评分/阶段或调用provider。测试与示例创建的数据库均为临时合成库。

正式部署和正式Tools注册尚未执行。当前家庭Compose仍为 `compose-practice-four-20261106.json`，镜像 `sha256:d94346e8ec8fada893f288aac5fddd8f26a1b6078d4eb23b1af9bfd2cc64e6cc`；本轮没有重建卷、重绑、重启或用旧Compose覆盖。保留原有未提交改动；未执行reset/checkout/clean/commit/push，没有读取根docker-compose.yml、batch_ingest.py、环境秘密或正式WebUI数据。只读Goal API返回null，没有创建/更新/完成Goal。

可导入源码为候选包中的 `open-webui-tools.py`，与仓库 `learning_service/tools.py` 完全相同。只导入Tools不能替代发布新学习API；需要在正式注册前确认用户“不读写正式WebUI data”的限制是否对这个新Tool作窄范围例外，或由管理员在UI自行导入。
