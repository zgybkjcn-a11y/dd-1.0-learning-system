# 家庭学习首页精简（2026-11-06，历史部署记录）

用户反馈“刷新今日任务”和重复的大题卡布局不清楚。已改为进入/返回首页、答题完成后自动刷新；默认折叠“自己挑一道题”，展开为紧凑列表；只有到期任务才显示复习区；移除“冒险起步2/3”模块。

该版已上线，随后被[三档应用题版本](adaptive-practice-2026-11-06.md)接续，勿再用本记录旧 Compose 覆盖新版本。

- 历史 Compose：`learning_data/deployments/family-math-20261105/compose-home-simplify-20261106.json`
- 镜像：`sha256:ab9e96eea6375c35f216402a11dbf06e96b5694524d2c541e5ed9f10f618b86f`
- 候选：`learning_data/release-preparation/dd-v1-family-home-simplify-20261106`，52 文件。
- source set：`5290cdeafda0715ebb54404db6ca5b123ddc71c8b7deb5c484b8b12f18c52df2`。
- 证据：`learning_data/verification/home-simplify-20261106/`；2 项真实控件浏览器测试通过（390/1280），部署源码/HTTPS/教材挂载验证通过。
- 备份：`learning_data/family-backups/family-home-simplify-preupdate-20261106`，校验值和 SQLite integrity 通过。

该次备份前52个测验会话、50次作答，上线检查时56个会话、53次作答。家长期间继续使用，新增记录保留，未用旧备份覆盖；家长1、档案2、题目14、绑定1、浏览器会话2、provider0。只更新家庭API/worker/gateway；原WebUI与代理ID/启动时间保持。后续三档版本进一步核对旧记录ID及原题/绑定内容保持。
