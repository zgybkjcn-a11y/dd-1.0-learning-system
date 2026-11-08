# A03：干净环境测试基础

日期：2026-11-07（Asia/Shanghai）。输入为 A01 后的 `main` / `deef3199f558ba72bbe3f2ff0c704586674a2232` 工作树，保留已有页级证据链、离线片段与文档候选。任务依据为[实施方案 A03](../plans/DD-1.0-NEXT-IMPLEMENTATION-2026-11-07.md)。

本批已完成可移植测试入口、干净环境复现和自动检查候选，不修改服务、Tool 或静态产品行为。**503 项单元/契约与 12 项浏览器用例通过，零失败、零跳过**。使用方法见[测试说明](../TESTING.md)，工程完成、交付与远端运行分别记录。

## 变更

- 开发依赖显式加入 `httpx==0.28.1`、`playwright==1.58.0`；`requirements-dev.lock` 固定 27 个直接/传递依赖及 SHA256。运行镜像依赖文件未改。
- 根 `conftest.py` 在收集和应用导入前隔离默认数据目录，移除继承的 provider/秘密文件配置，阻止测试 Python 进程的非 loopback DNS/socket 访问；不改变业务应用的导入行为。
- 将教材 PDF 夹具统一为运行时生成的原创文字、线段和图形；会话内生成母本，每个测试复制独立文件。临时参考 JSON 按这些 PDF 的哈希重新绑定，仍调用实际文件哈希校验、引用查询和渲染实现。
- 数学参考、只读 Tool、工作台、主站桥接不再读取本机教材目录。离线理解工坊由当前模板和合成服务响应即时生成，不依赖历史 HTML 或覆盖历史证据目录。
- 6 个浏览器测试文件共 12 个视口用例，统一 `browser` 标记；默认使用随 Playwright 固定的完整 Chromium 无头模式，也支持自定义路径和精确版本要求。缺模块/浏览器、版本不符或必需用例跳过均失败。
- `local_materials` 为显式实物组，默认排除。只在提供 `--textbook-dir` 时核对两册 PDF 的原件哈希与引用页可渲染性；不能据合成测试提升教材审核状态。
- 修正旧变式审核测试的完整响应期望：为既有 `textbook_scope`、`practice` 增加精确 `None` 断言，未删除完整比较或审核/私有归属/冻结断言。

## 干净环境

独立证据目录：`learning_data/verification/a03-portable-tests-20261107T091348Z/`。`workspace-before.json` 保存开始时 24 个脏文件的哈希；`files-before/` 保存需要继续编辑的既有文件。`clean-source/` 是 144 个源码/测试/静态资源/契约文件的白名单副本，不含教材、运行数据库、环境文件或 `learning_data/`，也没有复制根受限 Compose/导入脚本。

在该副本中创建全新 Python 3.12.12 venv，不启用 system site packages，按锁文件 `--require-hashes` 安装；`pip check` 无破损依赖。使用独立 `PLAYWRIGHT_BROWSERS_PATH` 下载 Chromium 145.0.7632.6（Playwright revision 1208）。本机原有 Linux 共享库与 Noto CJK 字体继续使用；这次验证是干净 Python/源码环境，不是新安装的操作系统。

锁文件 SHA256：`72c9bbe3e5c66b26a9e76a2cce533e3dcad079afddb9cc97f4c294f6cc87b18d`。源码指纹分别在 `clean-source-manifest-r1.json`、`-r2.json`、`-r3.json` 和 `-browser.json`；最终 `clean-source-manifest.json` 对应当前测试源码。`installed-packages.json`、`install.log`、`browser-install*.log` 保存安装事实。

初次标准浏览器安装的附加 Headless Shell 两次遇到 TLS 传输错误，重试后也已下载完成，保留到缓存外的 `unused-headless-shell-1208/`。最终入口使用 `channel="chromium"`，缓存里只有所需完整 Chromium/FFmpeg，`playwright install --no-shell chromium` 成功；无需 Shell 或本机 Google Chrome。

## 验证记录

实际工作目录为上述 `clean-source/`，执行：

```bash
../venv/bin/python -m pytest -q -m "not browser and not local_materials" --junitxml=../unit-r3.xml
../venv/bin/python -m pytest tests -q -m browser --junitxml=../browser-r1.xml
```

浏览器命令设置独立缓存，清除 `PYTHONPATH` 和自有浏览器覆盖变量。目录不存在任何实物教材；浏览器使用真实当前页面/脚本、ASGI API 和合成身份，外部 API 路由被拦截，离线 context 禁用网络。Python socket 保护不是操作系统级子进程网络沙箱。

| 检查 | 结果 |
| --- | --- |
| 单元/契约最终组 | collected 517，selected 503，**503 passed / 0 failed / 0 errors / 0 skipped**，14 deselected，147.87 秒 |
| 浏览器必需组 | collected 517，selected 12，**12 passed / 0 failed / 0 errors / 0 skipped**，505 deselected，413.10 秒；Chromium 145.0.7632.6，桌面 1280 / 手机 390 |
| 实物教材组 | **未运行**；默认排除的 2 项不能算通过 |
| 依赖/隔离故障检查 | 外部配置被覆盖且默认 app 只用临时目录、非 loopback 连接拒绝、缺 Playwright、缺浏览器、必需 skip、正确/错误自有浏览器版本共 6 类控制均达到预期 |
| 实物目录缺失路径 | 显式选择该组但不提供目录，2 个用例按预期失败，未读取教材；这是输入校验，非实物验收 |
| 原有候选保护 | 页级证据两个原有测试文件的 24 个 `test_` 函数 AST 全部保持；仅改夹具/导入。运行时源码、Tool、静态资源和离线片段脚本保持输入哈希 |

首次全单元组为 502 passed / 1 failed，原因是变式审核测试遗漏已经存在的两个空字段。补齐精确期望后全组 503 项通过。公共测试配置移至根目录后再次运行最终组通过；没有忽略或删除失败用例。配置浏览器时显式给 `tests -c pytest.ini`，避免 pytest 初次探测把自定义选项的路径值当成测试目标；最终路径/版本控制记录在 `controls-browser-version-r3.json`，早期探测失败日志保留。

本轮锁定的 Starlette 对 httpx TestClient 发出 1 条弃用提示；当前契约组通过，未为消除提示改运行依赖或切换 HTTP 客户端。安装依赖/浏览器的网络请求与运行测试分开；真实生成、embedding、外部 OCR 调用均未执行。

## 交付与接续

A03 本地出口已通过。[GitHub 自动检查](../../.github/workflows/tests.yml)在完成本地复现后加入，使用同一锁文件、Python 3.12、固定 Chromium、中文字体和两组测试命令；只上传合成 JUnit 报告。YAML 与命令/路径检查通过，**远端 CI 尚未执行**，工程代码/文档候选未提交。没有部署、注册/重绑、写生产向量或 Goal。

最终来源、依赖/状态/链接一致性及原改动保护检查见本批 `delivery-validation.json`；两组 JUnit 结果分别在 `unit-r3.xml`、`browser-r1.xml`，首轮失败及故障注入记录一并保留。回退仅撤销 A03 的测试基础与文档编辑，已有两份测试文件以 `files-before/` 为基准保留此前候选，不 reset/clean 整个工作区。

下一项 **A02**：把已有页级证据、离线片段、测试基础和计划文档整理为可审阅交付单元；提交/推送仍按届时有效指令处理。A09 的三个静态样本可独立继续准备，实物/家长/真实模型状态分别保留。
