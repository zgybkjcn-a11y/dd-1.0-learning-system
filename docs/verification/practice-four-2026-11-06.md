# 自动进阶改为四道不同题（2026-11-06）

用户指出两道题不足以判断是否可以尝试更高难度，建议3～5题。现采用中间值4：同一难度连续独立答对4道不同题，自动推荐下一档。只是进阶条件，不表示已经掌握整个章节。

界面显示当前累计与剩余数，例如“简单题已连续独立答对 2 / 4 道不同题；再答对 2 道后尝试进阶”。题库仍74题，各已覆盖章节每档4道应用题；不改题干、答案、判分或已存学习记录。

重复同一道题在一次累计中只算一次；错误或提示辅助中断累计并沿用巩固逻辑。清除本次累计的去重集合，避免有限题库中已经做过的题永远无法用于重新巩固升档。手动尝试更难一题不再立即抬高自动推荐；同档仍需4道。不同难度的正确题不混算；手动选档始终可用。

5项相关测试通过，包含手机390/桌面1280的真实控件检查：前1～3题不升档、第四题升档、逐题刷新保持计数、重复题不累加、提示后降档与明确重练后重新升档、手动难度/章节/档案隔离、解析与来源可见。证据 `learning_data/verification/practice-four-20261106/tests.log` 和 `browser/`。

当前Compose：`learning_data/deployments/family-math-20261105/compose-practice-four-20261106.json`。
镜像：`sha256:d94346e8ec8fada893f288aac5fddd8f26a1b6078d4eb23b1af9bfd2cc64e6cc`。
候选：`learning_data/release-preparation/dd-v1-family-practice-four-20261106`，57文件、schema11。
source set：`7fd549c86337114e2078e37c40920df8dfd1e341e3474a2e832736ece21d3c54`。
备份：`learning_data/family-backups/family-practice-four-preupdate-20261106`，SHA256与SQLite integrity通过。

使用固定本地依赖与基镜像禁网构建，仅替换家庭API/worker/gateway。部署验证见同证据目录 `deployed-verification.json`：线上实际模块验证1～3题不升档、第4题升档，UI提示、源码哈希、13册PDF、HTTPS及只读挂载正常；原记录ID与74题/绑定内容保持，原WebUI/代理未重启。新规则通过重算原作答历史生效，不改成绩。

保留所有未提交改动；不提交、不写Goal、不调用外部模型，不重复导入题库或重绑账号；其他教材/OCR与内容审核限制保持。保存当前输入后刷新即可使用。
