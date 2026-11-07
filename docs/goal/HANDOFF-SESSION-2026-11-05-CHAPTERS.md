# 家庭数学版：按单元 / 章节选择练习已上线

更新：2026-11-05 21:44（Asia/Shanghai）。用户要求按单元或章节选题。数学探险队首页现有单元选择卡片，选择后仅显示该单元题目；开始挑战、下一题循环和到期复习入口均跟随所选单元。答题页显示当前单元并提供“换个单元”。

当前二年级有“100以内加减法”4 题、“表内乘法”4 题；七年级有“有理数 · 减去负数”6 题。这是按现有知识目标组织的起步目录，未新增题目、教材章节编号或完整教材覆盖承诺。教材版本和后续题型仍可根据使用反馈补充。

首次进入默认选中本档案首个可用单元。同一档案刷新保留所选单元；旧界面当前题可在升级后恢复到对应单元。切换未完成题目的单元时询问是否跳过，取消切换会保留输入，确认后取消原未完成会话并切换；提交/判分期间限制切换。切换档案按已有上下文边界清理题目与单元状态。错题本的全部知识目标与自动分类继续可用。

相关验证 8 项通过：家庭 API 4 项、自动知识目标浏览器 2 项、冒险流程浏览器 2 项。最终补充后的冒险测试为 **2 passed in 19.06s**，涵盖 390px/1280px、单元题数、实际出题、下一题在单元内循环、刷新、旧页面恢复、未完成切换确认/取消、到期复习卡归属、错题本目标、档案隔离、无脚本错误和横向溢出。复习测试使用显式准备的合成复习卡；不是生产数据。未重跑旧 P0、四格式或全量验证。

预览：[二年级乘法单元](../../learning_data/verification/family-chapters-20261105/screenshots/grade2-multiplication-1280.png)、[手机单元选择](../../learning_data/verification/family-chapters-20261105/screenshots/grade2-multiplication-390.png)、[七年级单元](../../learning_data/verification/family-chapters-20261105/screenshots/grade7-home-1280.png)。

入口仍为 <https://172.19.116.53/learning/auth/login>。做完当前题并保存未提交内容后刷新，即可加载新版；已有登录和绑定保留。当前 Compose 为：

```bash
docker compose --env-file /dev/null -p dd-family-math -f learning_data/deployments/family-math-20261105/compose-chapters-20261105.json ps
```

固定镜像 `sha256:ab314b41d9b46500d02907649d43ce26f9ac1ccd1f7c155079e52f188d76b3bd`。50 文件候选相对上一版仅 `learning_service/app.py` 变化，schema 11。使用本地 OCI 基础镜像和锁定依赖、断网构建。初次沙箱构建被 Docker 权限阻止，失败记录留在 `build/`；成功构建在 `build-host/`。源候选与构建报告中的未部署状态是历史阶段，实际部署以独立记录为准。

上线前在线快照已导出到 `learning_data/family-backups/family-chapters-preupdate-20261105`，manifest SHA256 和 SQLite integrity 均通过后才切换。只更新家庭 API、worker、gateway 镜像；proxy、数据卷、网络、证书、原 WebUI 容器和 Tools 保留。四服务运行，API 健康；实际 `/ui` 包含单元功能且源码 hash 与候选一致，HTTPS `/health` 通过现有 CA 验证并返回 200。

**真实试用进展已变化**：更新前后均为家长记录 1、档案 2、题目 14、绑定 1、浏览器会话记录 1、学习会话 44、已判分作答 43（二年级 6、七年级 37），七年级另有 1 个活动会话。两档案已有真实作答记录；错题/手动错题为 0，实际刷新/切换体验尚未由家长确认。不能把旧交接中的“真实练习仍为 0”当作当前状态，也不能把聚合计数等同于完整试用验收。

证据：[部署记录](../../learning_data/deployments/family-math-20261105/deployment-chapters-20261105.json)、[备份校验](../../learning_data/verification/family-chapters-20261105/preupdate-backup-verified.json)、[浏览器报告](../../learning_data/verification/family-chapters-20261105/browser-report.json)、[构建记录](../../learning_data/verification/family-chapters-20261105/build-host/build.json)、[上线只读计数](../../learning_data/verification/family-chapters-20261105/runtime-postdeploy.json)、[实际 UI 检查](../../learning_data/verification/family-chapters-20261105/deployed-ui.json)。

继续收集单元选择和题型反馈，以及真实错题收藏、刷新/切换的使用体验。保留全部未提交改动，不 reset/checkout/clean/commit/push，不读改根 docker-compose.yml、batch_ingest.py、原 WebUI 数据或环境秘密；不调用真实模型/OCR、不外发学生资料、不写 Goal。学习 provider 保持 mock、外发关闭、预算 0。原完整 V1 的 T/QA/Goal 状态及复杂运维/其他学科暂缓范围不变。旧镜像与 Compose 保留；后续不要用旧 Compose up 回退新功能。
