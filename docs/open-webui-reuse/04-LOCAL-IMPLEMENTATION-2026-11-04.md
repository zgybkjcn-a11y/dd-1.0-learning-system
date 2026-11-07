# 现有 Open WebUI 复用：第一批本地实现与操作说明

首批工程历史说明；W04/W05/W06最新实现见[第二批操作说明](05-WORKBENCH-TOOLS-REVIEW-2026-11-04.md)。本文schema10/74项保留为首批证据。

日期：2026-11-04。用户已授权开始本地开发，并确认沿用当前 IP。目标入口为 **`https://172.19.116.53`（443）**，证书须含该 IP 的 SAN，并被访问设备信任。现有 `http://172.19.116.53:53001/` 与运行中的 WebUI 没有改动。本文件记录 W01–W03 与 W04 基础，不代表正式认证、部署或真实验收。

## 实现状态

| 工作包 | 当前产物 | 仍缺 |
| --- | --- | --- |
| W01 | 用户固定 IP/HTTPS 目标；只读 `ss` 未发现宿主 443 TCP 监听；身份协议设计 | IP 稳定性、证书/客户端信任、443 可绑定性与防火墙、HTTP53001策略及运维责任 |
| W02 | `login_gateway.py`、`gateway_http.py`：WebUI Cookie 验证、一次性登录 CSRF、服务器声明交换、来源身份比较、固定路由及最小转发 | 实际 WebUI 内置账号/Cookie、目标 TLS、网关容器/代理组合 |
| W03 | migration010、来源会话/当前绑定复核、共享上下文、事务内写入保护；安装/绑定 CLI 与撤权审计 | 正式安装 issuer、人工核对的身份/角色/学习者 manifest、操作人及目标学习库；正式库未初始化 |
| W04 | `/learning` URL、登录链接、上下文版本、旧标签页拒绝、身份/版本缓存命名空间 | 产品入口/完整上传测验恢复、两端 Tools 同步、完整界面与组合验收 |

数据库源码 revision10；API路径仍61、schemas仍22，新增 GET 使用既有 learner-context 路径。P0 保留 schema7；旧29文件候选保留 schema9，不和当前源码相等。

## 配置契约

示例与发布模板的秘密保持占位/空值。以下是需要协调的配置，当前没有向正式容器注入：

| 字段 | 本地实现约束/目标 |
| --- | --- |
| `DD_GATEWAY_ENABLED` | 默认0；单独网关进程，缺配置仍拒绝访问 |
| `DD_GATEWAY_PUBLIC_ORIGIN` / `LEARNING_BROWSER_ORIGIN` | 两端相同；拟用 `https://172.19.116.53`，只允许 HTTPS 默认443、无尾斜线/路径 |
| `LEARNING_PUBLIC_BASE_PATH` | API输出浏览器前缀；网关同值 `/learning`；内部 Tools/API URL 不加此前缀 |
| `LEARNING_SHARED_LEARNER_CONTEXT_ENABLED` | 通用默认0以保留旧接口兼容；复用网关模式必须1，旧模式的学习会话被网关拒绝 |
| `DD_GATEWAY_OPENWEBUI_URL` | 固定内部 `http://open-webui:8080`；认证 path固定 `/api/v1/auths/`、Cookie名固定 `token` |
| `DD_GATEWAY_LEARNING_URL` | 固定内部 `http://learning-api:8000`；不得发布宿主API端口 |
| `LEARNING_BROWSER_AUTH_SECRET/ISSUER/AUDIENCE` | 网关/API一致；新独立签名密钥，不能复制WebUI密钥、写入浏览器/Tools/日志 |
| `LEARNING_BROWSER_IDENTITY_PROVIDER/ISSUER` | provider为open-webui，issuer区分实际安装；和审核后的绑定清单一致 |

默认 OCR/诊断/变式均 mock、外发关闭、学习费用预算0。学习费用不覆盖现有 WebUI 聊天；聊天模型/费用/资料许可仍需独立准备。

## 网关行为与边界

浏览器通过 `GET /learning/auth/login` 获取表单，再 POST `/learning/auth/session`。只接受同一配置 Origin、同一 WebUI Token/subject 的一次性 nonce；nonce哈希保存在有界单进程内存中，120秒到期，重启后旧nonce失效。网关生成60秒HS256声明，仅在内部HTTP交换学习Cookie；不接受浏览器sub/role/account声明。WebUI `admin/user`仅作为入口状态，学习角色从数据库授权读取。

每次受保护请求重新验证WebUI Cookie，无身份缓存；API学习会话的provider/issuer/subject必须相同，当前绑定仍有效。WebUI过期/pending/身份切换、解绑或认证故障都拒绝访问。401/403清理浏览器学习Cookie；学习退出只撤销学习会话。`__Host-`Cookie始终Secure、Path=/、无Domain；会话HttpOnly，SameSite=Strict。

浏览器身份/adapter/learner头不转发；只转发两个学习Cookie、业务Content-Type、CSRF、上下文版本和幂等键。明确的方法/路径白名单阻止internal/docs和浏览器学习声明交换。新增API须单独审阅并加入白名单。WebUI认证响应token/个人资料/Set-Cookie全部丢弃，不回显异常正文；Learning Cookie只接收明确的两个名字并校验属性。

HTTP transport不用环境代理、不跟重定向、不自动重试；认证响应上限64KiB，连接后总截止3秒（含慢速状态行/头读取），业务转发30秒/32MiB。宿主DNS解析的系统阻塞上限尚未实测；目标组合须验证固定内部DNS与认证故障时间，不能把本地传输测试当成生产DNS故障验收。请求总量上限25MiB，multipart自身占用也计入；正式容量仍需实测。

登录页使用 `Referrer-Policy: same-origin`，保留同源表单Origin校验并避免跨源Referer；Chromium实测中no-referrer会令表单Origin变成null而被拒绝。nonce没有放在URL中。网关当前单进程，有界nonce不是多副本共享认证方案。

## 身份初始化与审阅流程

CLI：[manage_learning_identities.py](../../scripts/manage_learning_identities.py)。输入结构见[空模板](identity-manifest.template.json)。字段必须完整且无重复：accounts、learners、bindings、grants、revocations、unbinds，以及initialize_math布尔值。模板没有正式身份；只支持现有math-g7-v1与四种学习角色。不能按邮箱自动绑定，WebUI admin不自动成为学习admin。

下面只演示命令结构；本轮没有在正式库执行：

```bash
python3 scripts/manage_learning_identities.py validate --manifest /reviewed/path/identities.json
python3 scripts/manage_learning_identities.py plan --manifest /reviewed/path/identities.json --database /approved/learning-data/learning.db --operator approved-operator
```

先人工审阅身份清单、目标库、操作人、角色/范围和plan输出。apply还必须显式提供 `--reviewed-plan-sha256`，且action必须为apply；输入、目标、操作人或被管理状态变化会拒绝旧hash。validate不开库；plan不构造Database、不创建目录/新库、不迁移旧库，已有库用mode=ro事务快照。

apply在同一写事务中复核hash、执行必要迁移、绑定/授权/撤权并写audit_events；冲突全回滚。拒绝WebUI data目录、webui.db及数据库symlink。CLI是有主机权限的运维入口，operator是审计引用而不是独立登录认证；其执行权必须由主机运维权限控制。正式bootstrap/questions seed继续404。

撤权/解绑/角色变化撤销该账号所有学习会话、清空选择并递增已有上下文版本、消费旧挑战，保留资料/成绩。initialize_math只创建既有知识点、目标与数轴模板；不创建或批准母题，人工题库审核留W06。

## 共享学习者上下文

GET learner-context返回当前选择与整数版本；POST必须由浏览器受信会话/CSRF发起，携带expected_revision。相同选择幂等，切换版本递增并消费该账号旧挑战。浏览器不能用X-Learner-Id覆盖选择；每个业务读写提交版本，过期返回409要求刷新。写事务取得SQLite写锁后再次检查选择/版本/授权，防止授权检查后发生切换或撤权而写入另一学习者。

适配器可读取当前上下文，不允许选择；其显式learner不一致时拒绝，写操作也需版本。现有Tools尚未适配这一新模式，**W05需在每次调用前读取上下文并带版本，同时完成结果最小投影**；不能把共享上下文API完成当作两端Tools组合完成。

恢复副本撤销会话、清空选择/递增版本并消费未消费挑战；provider继续暂停，unknown费用占用保留。这里是本地副本验证，正式维护窗口、完整备份/恢复和RPO/RTO仍缺。

## 验证与下一批

测试使用合成身份、临时学习库、注入ASGI响应或loopback HTTP。浏览器探针拦截全部页面URL，用合成WebUI认证响应；ASGI的303返回已检查，后续导航由探针显式模拟；不能称为真实WebUI登录、TLS、模型tool call或最终可信回调。当前证据见[工程报告](../verification/open-webui-reuse-engineering-2026-11-04.md)、[浏览器记录](../verification/reuse-gateway-browser-2026-11-04.json)。

下一批先补W04完整工作台/恢复和W05 Tools上下文/输出边界，再做W06人工变式审核发布、W07独立sidecar/代理候选及新镜像。W01尚缺的证书/信任、HTTP策略和运维输入保持待确认，不阻止合成本地开发；真实组合、生产接入与试用仍按原阶段门推进。
