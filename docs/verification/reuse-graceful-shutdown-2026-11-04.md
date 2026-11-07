# W10 隔离 WebUI 停止流程补充

2026-11-04；承接[运行恢复报告](reuse-runtime-recovery-2026-11-04.md)和[W07–W10交接](../goal/HANDOFF-SESSION-2026-11-04-W07-W10.md)。[机器记录](reuse-graceful-shutdown-2026-11-04.json)保存实际时长、退出码、Docker信号事件与改动审计。

## 问题与修改

上一批两个新隔离WebUI在Compose stop后退出137、OOMKilled=false；旧停止入口仅因命令返回0便输出`stopped=true`，没有检查服务退出码。这会把超时强制结束当作成功停机。

本轮修改[隔离编排工具](../../scripts/probe_reuse_runtime.py)：停止宽限默认60秒，允许显式1–60秒；先读取固定project的容器ID和有限标签/进程元数据，拒绝外部project或未知服务，再按ID停止当时运行的容器。停止后核对容器集合、running/pid、退出码和OOM，出现137/143/非零、OOM、剩余进程或集合替换均报告failed且CLI退出1。已停止容器的历史失败不会被幂等重试改成成功；每次尝试写入新的`shutdown-*.json`，卷保留。

```bash
python3 scripts/probe_reuse_runtime.py stop \
  --directory learning_data/verification/reuse-shutdown-20261104/runtime \
  --stop-grace-seconds 60
```

这是新隔离project专用工具，不能用于原正式WebUI。没有修改固定WebUI镜像、启动脚本或正式容器停止策略。

## 证据与范围

只读检查上一批**隔离容器**中的start.sh确认最终以exec启动Python/uvicorn。旧日志未提供可定位137原因的充分信息。随后使用固定WebUI0.12.5镜像创建`dd-learning-reuse-shutdown-20261104`：新WebUI数据卷、两条internal网络、无宿主端口、OpenAI/Ollama关闭；只启动WebUI服务，没有运行完整业务/P0/四格式探针。

对同一新隔离实例进行以下针对性检查：

1. 健康后以60秒宽限停止：5.66秒，退出0，OOMKilled=false；Docker事件为SIGTERM和die0，没有SIGKILL。
2. 再启动，合成内置账号登录、确认模型列表为空并完成3次认证读取后停止：4.04秒，退出0，事件同上。
3. 再启动相同合成认证路径，使用修改后的停止工具验证；精确结果见机器记录的`tool_validation`。最终实例已停止，卷保留。

9项聚焦测试通过（0.08秒），覆盖正常退出/幂等、非零与OOM、仍运行、历史137保留、外部project拒绝、容器替换；[测试](../../tests/test_reuse_shutdown.py)。没有重新跑上一批56项、业务恢复、Tools、浏览器、P0或四格式。

上述实测确认本次受控合成场景可以正常停止；它不证明单纯延长超时修复了原两次137，也不证明正式负载下的停止/数据一致性。原137原因仍保留为未复现/未充分定位，后续实际负载停机、长连接/后台任务故障和完整架构恢复分别留证。不能把60秒写成正式RTO。

## 候选与状态

源码只有`probe_reuse_runtime.py`改变，新50文件候选为`learning_data/release-preparation/dd-v1-reuse-shutdown-20261104`，schema11/profile `reuse-runtime-v1`：

- 源码集合SHA256：`926d5738a04bdecc121e07c180be0446cd1b384ba3ed1f747befb0768f5bb954`。
- 归档SHA256：`2a5dacd79acfe096f1ca47541d05f24af1a8ee377561ce71a9b0e5aece80e0ef`。
- manifest仍`image_digest=null`；本轮未构建新镜像。Dockerfile、锁定依赖和30个学习代码/迁移文件与上一批构建相同，上一批学习image ID仍为`sha256:b67894e6bb8a7023d392a4dd4547e77b0c1d9b39912da3ddd1a50aefbd2b8cbb`。该旧镜像不是新源码包的构建证明。

所有旧源码候选/原运行记录保持。140个起点未提交文件的独立基线保存在`learning_data/session-audits/reuse-shutdown-20261104-start.json`；本轮核对见机器记录。T/QA状态保持，Goal API只读null、仓库blocked。正式IP/TLS/账号/Tools分享与模型最终原生回调、实际三通道费用/人工质量/完整架构恢复和试用门槛均保留；无生产变更、真实调用、资料外发或Git提交。
