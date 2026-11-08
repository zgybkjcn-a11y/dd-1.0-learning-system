# 可移植测试与本地材料验证

A08维护逻辑测试：`python -m pytest tests/test_readonly_tool_upgrade.py tests/test_main_study_tool_registration.py -q`，54项、纯临时SQLite，夹具仅合成身份/配置。`scripts/probe_tool_upgrade_native.py`需专用固定镜像断网挂载，不能在正式data中运行；命令与结果见[A08验收](verification/A08-tool-lifecycle-2026-11-07.md)。

A07新增 `tests/test_runtime_passages.py`、`test_runtime_passages_legacy.py` 与 `test_runtime_passages_browser.py`，全部使用合成正文/PDF；历史Tool 1.0.0/1.1.2源码仅作兼容夹具。实物回归输出留忽略目录，操作/结果见[A07验收](verification/A07-runtime-passages-2026-11-07.md)。运行模块不依赖scripts，契约快照纳入检查。

默认自动测试使用临时数据库、合成账号和运行时生成的 PDF，不需要 `learning_data/` 中的教材、历史截图或离线示例。教材哈希校验、章节/页码边界、引文身份和篡改拒绝仍执行原业务实现；测试只在临时参考 JSON 和内存目录中绑定合成 PDF 的哈希，不修改生产内容文件。

## 安装与执行

基准环境为 Python 3.12、Linux、Chromium。`requirements-dev.txt` 声明开发依赖，`requirements-dev.lock` 固定全部传递版本与分发文件 SHA256；开发环境安装锁文件，运行镜像仍使用原运行依赖。

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.lock
python -m playwright install --with-deps --no-shell chromium
python -m pytest -q
```

Ubuntu 上中文截图与 PDF 检查另需 `fonts-noto-cjk`。Playwright 1.58.0 决定默认下载的 Chromium 修订版；默认使用 `channel="chromium"` 的完整 Chromium 无头模式，不需要另下载 Headless Shell，也不依赖 `/usr/bin/google-chrome`。包/浏览器安装会下载测试工具，实际测试不调用真实生成、embedding 或 OCR 服务。

完整默认组包含单元/契约与 6 个浏览器文件（每个覆盖桌面和手机）。也可按以下组单独运行，显式 `-m` 会覆盖默认表达式：

```bash
python -m pytest -q -m "not browser and not local_materials"
python -m pytest -q -m browser
```

浏览器依赖或可执行文件缺失会报错，不能计为跳过。默认 `--fail-on-skip` 使任何已选测试的 skip/xfail 导致非零退出；标记排除显示为 deselected，不是通过或跳过。CI 必需组必须零失败、零跳过。

若明确验证另一套 Chromium，可配置路径和期望的完整版本号：

```bash
python -m pytest tests -c pytest.ini -q -m browser \
  --browser-executable /path/to/chromium \
  --browser-version YOUR_EXACT_CHROMIUM_VERSION
```

对应环境变量为 `DD_BROWSER_EXECUTABLE` 和 `DD_BROWSER_VERSION`。版本不符直接失败；结果输出实际 `browser.version`。指定自有浏览器的结果只覆盖该版本，不替代默认随 Playwright 固定的浏览器验收。

## 隔离与材料边界

根目录 `conftest.py` 在收集测试、导入应用之前清除继承的 `LEARNING_*`、`TENCENT_OCR_*`、网关和家庭设置变量，固定临时应用数据目录并关闭外部 provider 调用。传入自定义浏览器路径时保留上例的 `tests -c pytest.ini`，让 pytest 在解析路径参数前找到选项定义和正确项目。测试子进程继承这一隔离环境；需要验证配置的测试再显式设置自己的合成值。这样应用模块导入时创建的默认 app 不会打开项目已有数据库或读取环境中的秘密文件。

测试 Python 进程阻止非 loopback socket/DNS 请求；真实 HTTP 传输测试仅使用临时 loopback 服务。浏览器 API 路由全部拦截到 ASGI 合成服务，离线页面使用离线 context。Python socket 保护不是子进程或浏览器的操作系统网络沙箱，不能据此声称所有第三方进程都受网络命名空间隔离。

合成 PDF 明确写有 `SYNTHETIC`，包含原创文字、线段和图形，覆盖所需物理页数。会话内生成母本，每个测试得到独立副本；版本字典和临时参考文件的补丁在该测试后恢复。离线理解工坊由当前 HTML 模板与合成服务响应即时生成，不读旧 evidence 目录，不覆盖历史截图。

需要复核真正的本地教材时，另行显式运行：

```bash
python -m pytest -q -m local_materials \
  --textbook-dir /absolute/path/to/authorized-textbook-pdfs
```

这一组检查二上/七上两册原件哈希和引用页可渲染性，不重新作内容审核。未提供目录、缺文件、版本不符均失败；默认和 CI 都排除该组。未运行必须记为“未运行”，不能把合成测试通过写成实物教材审核通过。不要把教材或运行资料加入源码。

## 重现与维护

干净环境复现应把当前待审阅源码复制到一个不含 `learning_data/`、环境秘密和数据库的新目录，创建不带 `--system-site-packages` 的虚拟环境，并使用独立的 `PLAYWRIGHT_BROWSERS_PATH` 安装浏览器。保留源码文件哈希、锁文件哈希、Python/Chromium 版本、安装记录和各组 JUnit XML，分别记录 collected/selected/passed/failed/skipped/deselected。

依赖需要升级时，在 Python 3.12 环境更新直接版本，再使用 `uv pip compile --generate-hashes --output-file requirements-dev.lock requirements-dev.txt` 重新解析，并对受影响的组验证。锁文件不是运行镜像升级指令；本机浏览器/系统库变化也要记录。

GitHub 的[自动检查](../.github/workflows/tests.yml)在 main push、PR 或手动触发时按同一锁文件运行单元/契约和必需浏览器组，安装中文字体，保存合成 JUnit 报告；不读取本地材料，也不需要模型凭据。该配置只有提交并推送后才会在远端执行；本地通过不等于 GitHub 已通过。

相关工程证据见 [A03 验证记录](verification/A03-portable-tests-2026-11-07.md)，当前任务进度见[台账](plans/dd-next-work-tracker.json)。

## 冻结检索评测

A06 新增[离线评测规程](open-webui-reuse/retrieval-evaluation.md)与[基线报告](verification/A06-retrieval-evaluation-2026-11-07.md)。合成评分器测试和原片段测试共 73 项通过；运行 `python -m pytest -q tests/test_textbook_retrieval_evaluation.py tests/test_textbook_passage_sample.py`。真实 40 问及金标准仅留忽略目录，独立 CLI 显式固定输入哈希并写新输出目录；不加入默认测试，也不使用历史日期绕过有效期。退出 2 表示评测已完成但质量目标未达标。

A05 的[有界检索验证](verification/A05-chapter-retrieval-2026-11-07.md)新增 38 项合成契约，相关组共 241 项单元/契约、4 项桌面/手机浏览器通过；固定 WebUI 原生六方法/2 引用通过。命令及分母见报告，未重跑无关全套。真实补充 40 问和曝光记录只在忽略目录，A06 基线保持原样。
