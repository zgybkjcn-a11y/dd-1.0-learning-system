# 既有只读 Tool 升级与回退（A08）

本地维护候选已实现并验证，正式 Tool 未升级。目标固定为 `dd_family_study_readonly_v1`；新脚本 `scripts/upgrade_readonly_study_tool.py` 独立于首次注册脚本，不创建 Tool、不重绑账号、不改分享范围。仅支持固定 WebUI 0.12.5 SQLite 表结构和 A07 Tool 1.2.0，未来版本须重新验证及更新 pin。

## 准备输入与操作范围

脚本不默认指向任何数据库或容器，不读取环境秘密、其他用户配置或聊天，不调用 Docker、网络、模型，也不执行 Tool 源码。操作者明确提供现存 SQLite DB、后端源码根、候选源码、原生验证报告、预期旧源码 SHA256、预期归属账号 SHA256。所有读写查询限制为目标 Tool、其历史、其 access_grant 以及该归属账号的 role；不读取用户 settings。

候选固定：Tool 1.2.0 SHA256 `23fc5c2558a0141750031acaee434f7b0abd81d884974e8d15ee781c1f2404d7`；原生六方法规格与 metadata 分别固定 hash。脚本内 `BACKEND` 固定 A07 API、网关、配置、证据/检索模块、OpenAPI与引用桥接的9个文件。prepare、dry-run、apply、verify、rollback 均检查这些字节，写事务结束前再查一次。后端不相容则零写入。

`--backend-root` 必须来自将使用的相容服务/网关/静态桥接；本地源码路径检查只能证明给定文件，不证明生产进程正在运行它。正式操作前应在已授权维护范围内建立“活动服务/网关镜像及桥接→已验证源码根”的部署证据，先完成 A07 配套服务/网关/桥接验证，再升级 Tool。旧线上服务缺少页级 evidence，不能只换 Tool。片段开关默认关闭，材料校验和启用另按[A07运行契约](textbook-passages-runtime.md)。

本轮仅使用临时合成数据库。计划 A08 的正式维护条件仍适用：需要覆盖这个既有 ID 升级的有效维护指令；历史首次注册许可不自动扩展。以下命令是可审阅操作模板，不是本轮正式执行记录。

## 五阶段操作

所有路径由操作者明确填写；示例中的 `/isolated/...` 应先用于隔离候选。旧哈希和归属哈希来自受控准备步骤，不能从历史记录猜测正在运行的值。正式库读取也须属于已授权范围。

```bash
python3 scripts/upgrade_readonly_study_tool.py prepare \
  --db /isolated/webui.db --backend-root /isolated/a07-source \
  --source /isolated/readonly_study_tools.py \
  --native-report /isolated/native-result.json \
  --expected-old-sha256 <核对后的旧源码哈希> \
  --expected-owner-sha256 <既有归属账号的SHA256> \
  --destination /isolated/new-review-packet
```

prepare 以只读事务读取目标行、历史及权限，验证当前 version_id 对应合法的原生历史快照；目标不存在、旧哈希不符、归属/角色不符、公开共享、未知表结构或触发器一律拒绝。现有私有归属及明确的用户/组分享可保留，不新增或移除授权。旧版本缺历史、历史与当前配置不一致时停止，不能“修复后继续”。

准备包目录0700，文件0600，不覆盖已有目录。`package.json` 含目标完整旧行、历史和 opaque valves 等私有配置，用于精确回退，必须留本地私有目录；`review.json` 含源码差异、修改字段与状态哈希。终端只打印状态、哈希、固定Tool ID和操作ID。记录 prepare 返回的 `package_sha256`，逐阶段通过独立参数传入；不信任同目录自动读取的checksum。

```bash
python3 scripts/upgrade_readonly_study_tool.py dry-run \
  --db /isolated/webui.db --backend-root /isolated/a07-source \
  --package /isolated/new-review-packet/package.json --package-sha256 <准备包哈希>

python3 scripts/upgrade_readonly_study_tool.py apply \
  --db /isolated/webui.db --backend-root /isolated/a07-source \
  --package /isolated/new-review-packet/package.json --package-sha256 <同一准备包哈希>

python3 scripts/upgrade_readonly_study_tool.py verify \
  --db /isolated/webui.db --backend-root /isolated/a07-source \
  --package /isolated/new-review-packet/package.json --package-sha256 <同一准备包哈希>

python3 scripts/upgrade_readonly_study_tool.py rollback \
  --db /isolated/webui.db --backend-root /isolated/a07-source \
  --package /isolated/new-review-packet/package.json --package-sha256 <同一准备包哈希>
```

每步都核对数据库绝对路径hash、device/inode、目标完整状态、归属角色、分享和目标全部历史。文件复制/替换后须重新prepare；不能把一个库的包用于另一个库。支持SQLite WAL，读操作不建库；文件/目录祖先软链接拒绝。apply/rollback 用 `BEGIN IMMEDIATE` 锁定写事务，条件更新旧 version_id/content，更新目标行一次并追加历史一次，预期 `row_changes=2`。SQL authorizer限制可写表与列；触发器或额外表结构变化拒绝。插入历史或后端复查失败时事务回滚。

升级只改 content/specs/meta的manifest与has_user_valves/version_id/updated_at。name、归属、created_at、valves和meta其他值保持，全部access_grant与用户settings原样不动。版本历史采用原生 `tool_snapshot` 规则，不在历史里添加valves/specs。回退恢复准备时content/specs/meta等原值，追加回退版本，parent指向升级版本；version_id/updated_at按回退时间前进，不伪造“未升级过”。

同包重复apply或rollback返回row_changes=0。回退后旧包不能再次apply，重新升级需新prepare。竞争包、准备后任何目标配置/权限/历史变化、当前候选源码hash不符均拒绝，避免覆盖其他维护者更改。verify只确认已升级或已回退，prepared状态返回NOT_APPLIED。发生进程中断可用同包verify判定；事务已提交而日志遗失时重复执行不会重复写历史。

## 兼容与恢复顺序

| 组合 | 结果 |
| --- | --- |
| A07候选服务/网关/桥接 + Tool1.2.0 | 允许本工具准备与升级；默认关闭片段 |
| A05页级服务 + Tool1.2.0 | A07已验证页级兼容，但本迁移脚本要求完整A07源码，不用于正式跳过配套升级 |
| 历史正式旧服务 + Tool1.2.0 | 不相容，禁止单换Tool |
| A07服务 + 回退Tool1.0.0/1.1.2 | 保持页定位，无片段正文权限；先回退Tool并verify，再另行回退配套服务 |

固定镜像中 `get_tools` 比较缓存源码和当前数据库content，不一致会重新加载。A08原生探针验证了同一宿主请求缓存的升级与回退刷新。已在执行的调用仍可能完成；维护时避开在途聊天调用，数据库verify不代表真实模型已使用新版本。回退不删除此前聊天文字，也不修改全局模型/默认工具绑定。

本工具不是完整数据库/附件备份恢复机制；B07另行实现。包hash用于一致性，不是签名或防恶意管理员修改。给定backend-root的部署对应关系、目标旧哈希、归属和维护授权仍需正式维护操作单记录。

验证见[A08验收](../verification/A08-tool-lifecycle-2026-11-07.md)。本批维护包独立于A07的76文件服务源码包；无需修改服务release profile。首次注册脚本保持原样并继续拒绝不同源码覆盖。
