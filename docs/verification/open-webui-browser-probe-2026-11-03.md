# 隔离 Open WebUI 浏览器探针

日期：2026-11-03（Asia/Shanghai）  
范围：隔离 Open WebUI `dd-openwebui-isolated-20261103d`、隔离 Learning API、合成 trusted-header 身份；未使用正式 Open WebUI、真实学习者资料或真实 provider。

## 已执行

- 通过临时 loopback 转发访问隔离 Open WebUI，浏览器请求带有该实例配置的 `X-Auth-Request-Email`、`X-Auth-Request-Name` 和 `X-Auth-Request-Role` 合成身份头。
- Chromium `domcontentloaded` 后等待前端初始化；首页返回 HTTP 200，标题为 `Open WebUI`，可见 `DD UI Probe`，无 `pageerror`。
- 访问 `/workspace/tools` 后，页面初始化请求 `/api/v1/tools/` 返回 HTTP 200；会话读取到 1 条隔离 Tool 记录，名称为 `DD Learning V1`，manifest 声明 Open WebUI 0.12.5，公开方法规格为 11 个，包含 `start_trusted_interaction`。
- Tools 管理页面无页面脚本错误；在 390px 之外的本探针不作布局结论，窄屏工作台证据仍见 `browser-ui-2026-11-03.json`。

## 结果边界

本探针证明隔离实例的 trusted-header 登录、前端初始化、Tool 列表读取和注册记录可由真实浏览器访问。隔离实例没有可调用的真实模型/provider，因此没有从聊天页面产生真实模型 tool call，也没有完成浏览器端最终 `input`/`confirmation` WebSocket 回调、上传→复核→确认→测验提交链路。原生 loader 使用合成回调的证据仍见 `open-webui-tools-registration-2026-11-03.md`，不能替代本项待验收内容。

探针完成后已移除临时 loopback 容器和 `/tmp/dd-openwebui-loopback-proxy.py`。后续清理从隔离 Open WebUI SQLite 中精确删除了探针创建的 1 个合成用户及其 1 条 auth 记录；确认没有其他表引用该用户 ID，保留现存隔离管理员与 `dd_learning_v1` Tool。清理后 Open WebUI `/health` 为 HTTP 200，隔离 Learning API 和 Open WebUI 均保持运行；正式 Open WebUI 未操作。
