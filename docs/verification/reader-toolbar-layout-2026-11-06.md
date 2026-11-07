# 教材目录宽度与阅读工具栏调整

2026-11-06，按用户要求缩窄左侧目录、扩大右侧教材页，将“当前范围、展开本页、收起本页”移入翻页/跳转工具栏右侧。

目录在桌面随视口取136～168像素宽（原220像素），两栏间距从16改为12像素，教材图像使用右侧可用宽度。工具栏以弹性布局排列，范围和折叠控件靠右；空间不足时自动换行。移动端保留可收起目录，不强行挤成两栏。仅改动 `learning_service/app.py` 的样式和HTML布局，没有更改范围选择、出题、检索、翻页、缩放或数据逻辑。

使用合成身份和真实地理教材原图检查390、768、1024、1280、1440像素共五种视口。1024及以上，翻页、跳转和右侧范围/折叠处于同一行；所有视口无横向溢出和页面脚本错误。实际点击前后翻页、展开/收起及原图放大通过。1280像素下目录宽166.4像素，原图宽819.6像素。此为布局变更，未增加单元测试或重跑无变化的API全套测试。

- [布局检查数据](../../learning_data/verification/reader-toolbar-20261106/layout-report.json)
- [桌面截图](../../learning_data/verification/reader-toolbar-20261106/reader-1280.png)
- [手机截图](../../learning_data/verification/reader-toolbar-20261106/reader-390.png)
- [上线核验](../../learning_data/verification/reader-toolbar-20261106/deployed-verification.json)
- [部署记录](../../learning_data/deployments/family-math-20261105/deployment-reader-toolbar-20261106.json)

当前Compose：`learning_data/deployments/family-math-20261105/compose-reader-toolbar-20261106.json`；镜像：`sha256:82a2388392bc6577a9775d1a6188a21b94924a7c3af87dbfbbf8082d0b3dc9b6`。52文件候选 `dd-v1-family-reader-toolbar-20261106`，source set `6744828f22c59fc905304d209531a3a5ec24a191057760198192ae1435feb99f`，禁网构建并逐个核对源文件哈希。上线前备份 `learning_data/family-backups/family-reader-toolbar-preupdate-20261106` 已校验。

仅更新家庭API/worker/gateway；原WebUI/代理、网络、TLS、数据卷和教材挂载保持。上线后核对实际UI/源码、服务健康、HTTPS及登录跳转，并比较学习数据计数。原14题、两个档案、一个家长绑定、50次作答/判分及其他计数均保持；教材与权限边界见[统一阅读器记录](unified-textbook-reader-2026-11-06.md)。所有未提交改动及旧部署记录保留，不提交、不推送、不写Goal。家长刷新后实际视觉反馈仍待确认。
