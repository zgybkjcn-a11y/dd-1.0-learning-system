# A09 三个静态样本交付准备验收

2026-11-08（Asia/Shanghai）：工程候选就绪；交付为 candidate_only，实际设备/家长验收 pending，总状态 open。发布和家长反馈不由自动化代签。下一项可继续 B01 的七上第二章覆盖表。

证据目录 `learning_data/verification/a09-static-samples-20261107T223140Z/` 以 UTC 命名，对应北京时间 11 月 8 日。操作和设备检查表见[静态样本交付与恢复](../open-webui-reuse/static-samples-delivery.md)。

## 本地改动与交付物

`scripts/prepare_main_study_samples.py` 改为显式 `prepare/verify`，要求独立输出目录和 `samples-*` 名称，从固定提交 `deef3199f558ba72bbe3f2ff0c704586674a2232` 提取并逐个核对九个文件。旧固定输出不再复写；工作树中 A07 的桥接脚本不作为样本输入。

原配置、三条 alias 和四份旧静态文件都固定哈希；新包包含候选、原配置、回退资源、配置双向差异、静态差异和清单。检查异常路径/软链接、已有输出、静态命名冲突、准备期间输入变化和包篡改。外部审阅清单哈希用于 verify；本地基线验证与实际运行验证有明确边界。

`scripts/probe_main_study_samples_nginx.py` 接受独立包和新结果目录，先核对包再启动临时 nginx。固定镜像、禁止拉取、断网、无宿主端口，挂载仅本包及新建临时自签证书；候选和回退分别验证，成功/失败回执及容器清理独立记录。没有发布命令或活动配置写入。

包 `release-packet/manifest.json` SHA256：`c149f286216d72cf28da7901f6d528627b45d5d9d285d5495478ba32b397043e`；其中 19 个文件另加清单共 20 个文件。新静态名 `samples-20261108-a09`，回退名 `chat-20261107`。Mermaid 来源固定为 11.12.1；bundle、SRI、MIT、67 个依赖许可文件全部保持历史版本。未引入新依赖。

## 本轮验证

- `packet-tests.log` / `packet-tests.xml`：30 项通过。用合成静态内容验证移动包仍可校验、配置补丁正反向恢复、旧文件与活动输入保持、拒绝覆盖/路径/软链接/基线变化/包篡改；nginx 语法失败的合成分支确认清理并写 failed，禁止进入 HTTP 检查。
- `source-tests.log` / `source-tests.xml`：最终源码副本用 A03 锁定 Python 环境再次运行同一组，30 项全部通过，零失败/跳过，验证最终交付版本。
- `nginx-probe-r3/nginx-isolated.json`：真实固定 nginx 隔离检查 passed；候选 4 条和回退 3 条 HTTPS 静态路由，均 200/no-store、正确 MIME、正确文件 SHA256，两个临时容器已移除。回退使用本包保存的原配置和旧资源，不借助线上资源。
- `nginx-probe/` 与 `nginx-probe-r2/` 保留前两次 failed：改写探针时误抄镜像摘要长度，Docker 在启动前拒绝，未尝试拉取。第二次补齐 stderr 记录确认原因；修正为原脚本的完整 digest 后 r3 通过。失败不计入通过次数。
- `evidence-reuse.json`：9/9 新包文件与固定提交、旧候选哈希一致；10 个历史证据文件建立哈希索引。旧证据全目录和原有脏文件的前后指纹在最终校验中对比。
- `source-manifest.json`、`increment-manifest.json`、`a09-increment.patch`：保存最终源码、逐文件增量和回放依据；`delivery-validation.json` 汇总必要出口和历史保全。

测试入口：A03 venv 的 Python 运行 `-m pytest -q tests/test_static_samples_packet.py`。测试只用合成旧资源与候选资源，nginx 实物验证另使用固定历史样本包。没有重跑未变化的整套后端/浏览器测试。

## 复用证据与验收边界

[历史三样本报告](main-study-samples-2026-11-07.md)的最终浏览器两视口（1280/390）、各 26 组等式操作、先预测门槛、路线跳转原页/练习、草稿与进行中练习保持、范围/身份竞态、公开投影、无外部资源请求等继续有效于同字节静态包。实际 WebUI 0.12.5 前端的历史拦截 API 验证也保留原范围。A03 另有可移植完整桥接验证；此次没有把 A07 桥接结果用于旧静态包。

历史 `chapter-review-{1280,390}.pdf` 确为 Chromium 生成的三页 PDF，含中文、公式、页码和链接，无 A4 裁切；系统打印对话框在自动化中由桩替代。四个未改字节实物复制至 `device-preview/`，便于审阅；新脚本封包不会改变 UI 功能。自动截图、PDF 和模拟手机宽度不能代替实际家庭手机触屏、真实打印机和家长意见。

兼容结论限已验证的历史家庭服务/WebUI 0.12.5/旧桥接组合。A07 服务/Tool1.2.0 有独立候选，不混入本包；未来发布它们要重新核对组合。本轮仅读取本地活动 nginx 配置、四个旧公开静态文件及 Compose 中代理的静态/配置映射，未刷新容器运行状态。运行观察时间仍为 A01 的 `2026-11-07T17:00:53+08:00`，不得将包的生成时间当成线上检查时间。

未 commit/push/部署，未读正式 Tool/data、未调用真实模型或外部 OCR、未写生产向量、未修改 Goal。全部原有未提交改动及历史候选保留；A02 仍为已整理待提交。本批只提升 A09 工程状态，实际发布/设备验收仍待满足。
