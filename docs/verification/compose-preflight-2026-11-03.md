# 隔离 Compose 静态前置检查

日期：2026-11-03（Asia/Shanghai）

## 检查范围

`python3 scripts/check_isolated_compose.py` 仅运行 `docker compose config --format json` 并检查解析后的配置，不启动、停止或重建容器，也不连接现有 Open WebUI。检查只针对仓库受跟踪的 `docker-compose.learning.yml`；测试 Compose 覆盖文件和外部实际服务须另行审阅。

执行结果：通过。配置只有 `learning-api` 与 `learning-worker`，二者仅接入 `internal=true` 的 `learning-internal` 网络，只挂载 Compose 管理的 `dd_learning_data` 卷；无宿主端口、bind mount、特权、host namespace、额外设备或 capabilities，`LEARNING_DEV_MODE=0`，三个 provider 均为确定性 mock。解析用的临时密钥只存在于 preflight 子进程环境，不打印到输出或写入仓库。

检查器拒绝额外服务、非 internal/external network、外部卷/host driver options、宿主端口、bind mount、provider 替换、开发模式、提权或 namespace/设备旁路。其六项回归均通过。

## 验证命令与结果

- `pytest -q tests/test_isolated_compose.py`：6 passed。
- `python3 scripts/check_isolated_compose.py`：通过；未启动容器。
- `python3 -m compileall -q learning_service tests scripts`：通过。
- `python3 scripts/verify_goal_consistency.py`：通过。
- `git diff --check`：通过。

本检查只验证当前受跟踪 Compose 配置的静态边界，不证明运行时主机防火墙、daemon 全局配置、Open WebUI 持久化连接、真实 endpoint egress 或服务故障恢复。未执行数据库服务、对象存储或真实 provider 网络故障演练；T21/T22 的这些验收仍待独立获准环境。检查器不是生产切换授权，也不改变 Goal 状态。
