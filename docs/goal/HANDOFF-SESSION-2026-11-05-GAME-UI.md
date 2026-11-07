# 家庭数学版：数学探险队界面已上线

最新续跑补充（2026-11-05 21:44）：**单元 / 章节选择已上线**，先读取 [单元选题交接](HANDOFF-SESSION-2026-11-05-CHAPTERS.md)。当前 Compose 为 `compose-chapters-20261105.json`，按所选单元出题、下一题和到期复习；更新前后学习计数一致。真实两档案已有 43 次已判分作答（二年级 6、七年级 37），错题试用和实际刷新/切换反馈仍待确认。下文旧部署、零作答及待绑定状态均为历史；现有登录绑定保留，所有未提交改动和执行限制继续适用。

更新：2026-11-05 20:54（Asia/Shanghai）。用户反馈原工作台没有使用兴趣，并明确选择“活泼闯关：更明亮、带鼓励和进度”，随后要求继续。家庭版已按此风格实现、验证并部署。

界面现在分为冒险首页、挑战答题和错题收藏三个入口。顶部用两个档案卡片切换：二年级为数字森林，七年级为星球探索。首页有主题插画、明确的开始按钮和可直接选择的挑战卡片；答题页面突出题面、输入和判分反馈，可继续下一题、查看提示或请家长复核；错题收藏保留自动知识目标、手动修改及分档案保存。

完成练习、独立作答和错题数量均来自当前档案实际数据。冒险起步的三步按档案选择、真实完成作答、真实收藏显示，不虚构星级、连续学习日或排行榜。插画是本地内联 SVG，不请求外部图像服务，不启用模型/OCR。调试 ID、原始响应及家庭版不可用入口不出现在普通使用界面。

功能及浏览器验证 **8 passed**：家庭 API 4 项、自动目标浏览器 2 项、冒险流程浏览器 2 项。390px/1280px 均覆盖档案卡片、开始练习、提交前后刷新恢复、答对/答错反馈、下一题、提示影响独立作答、错题自动目标/保存/刷新、切换后内容清理与进度隔离，无脚本错误或横向溢出。十张截图已人工查看主要页面，均使用合成数据；不是家长真实试用记录。

预览：[二年级首页](../../learning_data/verification/family-game-ui-20261105/screenshots/grade2-home-1280.png)、[七年级首页](../../learning_data/verification/family-game-ui-20261105/screenshots/grade7-home-1280.png)、[手机七年级](../../learning_data/verification/family-game-ui-20261105/screenshots/grade7-home-390.png)、[错题收藏](../../learning_data/verification/family-game-ui-20261105/screenshots/grade2-notebook-390.png)。

当前入口仍为 <https://172.19.116.53/learning/auth/login>。家长真实登录和启用码绑定已在此前完成；同一家长启用码可留空。页面已打开时，先保存未提交内容，再刷新以加载新界面；会话过期时重新登录。

运行镜像：`sha256:02f338a3ef0fceeb7846b7692edd48aee3574c6e2774aec99f4f9502dd59d005`。当前 Compose：

```bash
docker compose --env-file /dev/null -p dd-family-math -f learning_data/deployments/family-math-20261105/compose-game-ui-20261105.json ps
```

更新只替换家庭版 API、worker、gateway 的固定镜像，proxy、网络、证书、数据卷和原 WebUI 容器保持。新 50 文件候选相对上一版只有 `learning_service/app.py` 变化；schema11、契约、模型配置和 Tools 未改。旧镜像、Compose 和交接证据保留，避免使用旧 Compose 的 `up` 回退新版。

实际部署核对：四服务运行、API 健康、HTTPS health 200，新服务提供的 UI 与候选/工作区源码 hash 一致。家长记录 1、档案 2、题目 14、身份绑定 1、浏览器会话记录 1；实际练习、作答、错题和 provider 调用仍为 0，更新前后计数/档案一致。真实两档案试用仍待家长操作，完整 V1 的 T/QA/Goal 状态未提升。

更新前已在持久数据卷 `backups/family-game-ui-preupdate-20261105` 生成在线快照，成功导出到[本地备份](../../learning_data/family-backups/family-game-ui-preupdate-20261105/)，检查 manifest SHA256 与 SQLite integrity 后才切换服务。此步骤没有重建或恢复生产数据库。

证据：[部署记录](../../learning_data/deployments/family-math-20261105/deployment-game-ui-20261105.json)、[浏览器报告](../../learning_data/verification/family-game-ui-20261105/browser-report.json)、[备份验证](../../learning_data/verification/family-game-ui-20261105/preupdate-backup-verified.json)、[构建记录](../../learning_data/verification/family-game-ui-20261105/build/build.json)、[实际页面检查](../../learning_data/verification/family-game-ui-20261105/deployed-ui.json)。源码候选和构建报告的未部署字段仍是各阶段历史边界，实际部署以本次独立记录为准。

下一步优先收集这两个年级的界面与题型反馈，完成各一道题、判分/刷新、切换和错题收藏的真实试用。继续保留全部未提交改动；不 reset/checkout/clean/commit/push，不读改根 docker-compose.yml、batch_ingest.py、原 WebUI 数据/环境秘密，不真实模型/OCR或资料外发，不创建/更新/完成 Goal。原完整 V1、复杂监控、商业化和其他学科仍暂缓；无变化的旧 P0、四格式和全量验证未重跑。
