# A08 既有 Tool 升级与回退本地验收

2026-11-07（Asia/Shanghai）。已实现并验证独立 prepare/dry-run/apply/verify/rollback，目标固定 `dd_family_study_readonly_v1`，候选仍为A07 Tool1.2.0。**54项单元/事务检查通过，固定WebUI0.12.5原生升级、回退、历史及缓存检查通过。** 正式Tool未读取、升级或重绑；下一项A09。

## 实现

入口 `scripts/upgrade_readonly_study_tool.py`，操作与边界见[维护操作单](../open-webui-reuse/tool-upgrade-rollback.md)。原 `register_main_study_tools.py` 未修改、未执行正式注册。

准备包固定目标旧源码hash、归属hash、完整目标行/历史/access_grant、数据库文件身份、A07后端9文件hash，以及原生验证的1.2.0源码/六方法规格/metadata。未知表结构、触发器、缺历史、公开共享、hash或配置变化均拒绝。临时库写事务只更新目标行及追加一条合法history，SQL authorizer限制列和表；异常整笔回滚。其他Tool、用户settings、模型、聊天及权限记录不变。回退也核验当前完整候选状态，恢复原content/specs/meta/配置并追加原生回退历史；重复调用幂等，旧包回退后不能重新升级。

脚本只用标准库，不导入WebUI运行配置/秘密，不调用网络、Docker或模型，不执行Tool源码。CLI只打印哈希和状态；私有包0700/0600，包含目标旧配置，不能加入公开提交。后端hash检查证明给定源目录，不证明生产进程使用它；正式执行仍需授权内的活动部署对应证据，不能拿本地候选冒充已部署后端。

## 证据与结果

证据目录 `learning_data/verification/a08-tool-lifecycle-20261107T144058Z/`。开始保存已有未提交文件与HEAD/index指纹；前序候选保持。新增实现、测试、操作单形成独立增量；A07服务代码、Tool源码、教材材料、原生验证与release包未改。

- `unit-r1.xml/log`：首轮50项通过。
- `unit-r2.xml/log`：54项通过、零失败/错误/跳过。覆盖私有和明确共享权限保全、旧hash/owner/role/目标缺失、schema/触发器、准备后content/specs/meta/valves/name/owner/时间/权限/历史变更、并发同包幂等、竞争包拒绝、history冲突回滚、写入后backend变更回滚、WAL与新包再次升级、包篡改/复制数据库/软链接、读取范围和日志脱敏；含原注册测试。
- `upstream-source.json`：从固定镜像读取tools/tool_history/access_grants三个源码的hash，无生产挂载；原生历史snapshot语义据此实现。
- `native-command-r3.json`、`native-exit-r3.json`、`native-r3.log`、`native-result.json`：固定镜像在断网、只读根、临时data中运行原生迁移生成数据库，插入合成目标/用户/权限；执行五阶段及重复操作。原生Tools读取与get_tools六方法均通过，同一缓存升级和回退均重新加载；原生tool_snapshot一致，历史共3条，其他表记录完全一致，模型调用0。
- 前两次容器准备未进入断言：输入文件父目录未先创建、只读嵌套挂载点不存在。改为预先准备完整单一挂载目录后通过。失败日志保留；镜像导入尝试写static在只读根被拒绝的日志不影响本探针断言。没有正式容器/数据挂载。

只复验本批新增维护逻辑及既有注册保护，没有重跑A07输入未变的688后端、6浏览器或实物题集。原生探针新增实际迁移schema、history/caching检查；不是实际模型或真实家长聊天验收。

## 交付与续接

`source-manifest.json`与`maintenance-packet/`固定独立维护脚本、探针、测试/合成夹具及操作说明；`synthetic-demo/`提供只含合成身份的可审阅prepare包与升级/回退结果。`increment-manifest.json`、`a08-increment.patch`、`increment-replay/`记录本批相对原工作树的改动；`delivery-validation.json`核对hash、回放、HEAD/index、原有改动、文档链接和历史材料保全。

工程与本地验收完成，交付状态candidate_only；未提交、推送、部署、改正式Tool/分享/全局模型，未调用真实模型或OCR，未写Goal。A02仍已整理待提交、总状态open。正式Tool仍仅A01沿用的历史1.0.0记录，本批未重新回读。线上观测继续固定2026-11-07 17:00:50–17:00:53 +08:00。

下一项 **A09：三个静态样本交付与设备体验**。先核对已提交样本/旧证据，使准备脚本支持新独立输出目录，准备静态差异和反向恢复集合；候选准备、实际发布、家长桌面/手机/打印反馈分开记录。当前工作树family-bridge属于A07片段候选，不能直接混入历史静态样本包或覆盖线上。
