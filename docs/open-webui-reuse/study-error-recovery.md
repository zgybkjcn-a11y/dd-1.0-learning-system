# 学习会话、网关与只读 Tool 故障排查

2026-11-07，A04 本地候选。六方法 Tool 为 **1.1.1**，正式 Tool 仍只沿用 1.0.0 的历史注册证据，未升级或重新读取正式库。工程验证见[A04 报告](../verification/A04-study-errors-2026-11-07.md)。

## 用户恢复方式

| 现象 | 网关分类码 / HTTP | Tool 分类码 | 用户操作 |
| --- | --- | --- | --- |
| 主站没有登录或登录已被拒绝 | `WEBUI_LOGIN_REQUIRED`、`WEBUI_LOGIN_REJECTED` / 401 | `LOGIN_REQUIRED` | 登录主站，再从家庭学习入口进入 |
| 已知、未撤销且仍有绑定的学习会话过期 | `BROWSER_SESSION_EXPIRED` / 401 | `SESSION_EXPIRED` | 重新进入家庭学习；无需重绑账号 |
| 缺少、未知、已撤销或绑定已撤销的学习会话 | `BROWSER_LOGIN_REQUIRED`、`BROWSER_SESSION_INVALID` / 401 | `SESSION_INVALID` | 重新进入家庭学习；不推断为账号错绑 |
| 主站身份与有效学习会话实际不符 | `LEARNING_IDENTITY_MISMATCH` / 401 | `IDENTITY_CHANGED` | 已停止读取；确认主站账号后重新进入。Tool 宿主用户不符或前后 account 变化也使用此类 |
| 当前档案或 revision 已变化 | `LEARNER_CONTEXT_CHANGED` / 409 | `CONTEXT_CHANGED` | 丢弃旧资料，刷新并重新选择档案和书章 |
| 尚未选择档案、参数不在当前范围 | 范围类错误 / 422、页范围错误 / 404 | `CHOOSE_PROFILE`、`INVALID_SCOPE` | 从当前档案的目录重新选择，不自动切换到其他孩子或教材 |
| 教材原件缺失或版本不符 | `TEXTBOOK_PAGE_UNAVAILABLE`、`MATH_REFERENCE_TEXTBOOK_UNAVAILABLE` / 503 | `TEXTBOOK_UNAVAILABLE` | 请维护者核对材料；不是重登录提示，也不是内容不存在结论 |
| 当前范围没有精确映射 | `MATH_REFERENCE_NOT_FOUND` / 404 | `REFERENCE_NOT_FOUND` | 查看已列出的目录或项目，不编造原文/答案 |
| 教材检索超时 | `TEXTBOOK_RETRIEVAL_TIMEOUT` / 504 | `RETRIEVAL_TIMEOUT` | 稍后重试；不以超时判定“教材没有相关内容” |
| 检索返回故障 | `TEXTBOOK_RETRIEVAL_UNAVAILABLE` / 503 | `RETRIEVAL_UNAVAILABLE` | 稍后重试或打开原页；不返回旧证据 |
| 登录校验或学习服务超时 | `AUTH_UPSTREAM_TIMEOUT`、`LEARNING_UPSTREAM_TIMEOUT` / 504 | `AUTH_TIMEOUT`、`SERVICE_TIMEOUT` | 稍后重试；不报告身份冲突 |
| 登录校验或学习服务不可用 | `AUTH_UPSTREAM_UNAVAILABLE`、`LEARNING_UPSTREAM_UNAVAILABLE` / 503 | `AUTH_UNAVAILABLE`、`SERVICE_UNAVAILABLE` | 稍后重试，持续失败时提供请求编号 |
| CSRF、来源、重复 Cookie/请求头等校验失败 | 对应拒绝码 / 400、401、403、413、404 | `REQUEST_REJECTED` | 刷新后重试；原有校验保持，不能绕过 |
| 响应格式、来源身份或引用字段不可信 | 上游/检索 `*_INVALID` / 502；资料版本错误 / 503 | `REFERENCE_INVALID` 或 `AUTH_UNAVAILABLE` | 停止引用，稍后重试或联系维护者 |
| 无法可靠识别的失败 | `STUDY_REQUEST_UNAVAILABLE`；保留业务 HTTP 状态，未知异常 503 | `STUDY_REFERENCE_UNAVAILABLE` | 明确暂不可用，不猜测错绑或直接展示原始异常 |

Tool 输出包含 `error`、固定中文 `message`、`action`、`retryable`、`request_id` 和固定 `workbench_url`；错误时没有旧 pages/concepts/questions 或新 citation。空证据的正常检索仍走成功结果 `grounding.status=no_evidence`，不会把服务失败伪装成空命中。回调抛异常时返回 `CITATION_UNAVAILABLE`，不暴露异常内容；若回调此前已接收部分引用，本批没有宿主撤回事件协议，不能宣称已撤回那些事件。

## 请求编号和维护排查

网关为每次请求生成随机 `ddreq_` + 32 位十六进制编号，放在 `X-DD-Request-ID` 响应头和错误 JSON 中。客户端传入的同名请求头被忽略。它不由 Cookie、用户或学习者 ID 派生，不改变身份校验，也不作为授权凭据。

Tool 只接收内部网关响应头中符合该格式的编号，错误正文中的编号、消息和 details 不被采用。由 Tool 本地校验、网络或未知异常导致的失败使用 `ddtool_` + 随机编号；网络失败时尚未拿到网关编号，不能声称它能直接对应某条网关日志。网关返回的错误则由两侧日志共享该次 `ddreq_` 编号。

应用新增的日志只有固定字段：

```text
dd.study.gateway: study_failure request_id=ddreq_<32 hex> code=<allowed code> status=<HTTP status>
dd.study.tool: study_failure request_id=ddreq_<32 hex 或本地 ddtool_32hex> code=<allowed code>
```

这些行不含 Cookie、账号、学习者标识、查询词、答案、URL 参数、上游消息或 traceback。网关继续禁用访问 URL 日志；本改动不控制所有第三方或宿主日志设置，也没有新增持久日志卷、外部通知或运行监控。

维护者先按请求编号找到固定分类，再根据该类检查服务可达性或对应材料版本。不要为排错导出完整环境变量、浏览器 Cookie、聊天或正式数据库。身份不符也不会自动重绑、重建卷或覆盖现有 Tool。

## 兼容与边界

错误细分改变了两类历史 HTTP 结果：明确超时返回 504；身份响应格式损坏返回 502，合法但被禁用的角色仍为 401。学习服务的原始错误只在只读教材/参考路由按允许的“错误码 + 状态”重新构造；其他业务成功响应和写操作流程保持原契约。身份 Cookie、Origin/CSRF、固定内部主机/路由、返回体长度、查前查后档案检查继续执行。

请求编号是每个网关 HTTP 请求的关联标识，尚不是端到端分布式追踪。Tool 检索请求自身网络超时也显示检索超时，表示该次检索调用没有完成，不断言服务端具体在哪一步超时。真正过期只在后端确认会话仍绑定且未撤销时返回；旧后端若只有通用失效码，新 Tool 仍可显示重新进入，无法自行知道是否过期。

页级引用、版本身份和教师/判分边界仍有效；五片段尚未接入。升级必须保留匹配的服务、网关和 Tool 组合，正式升级/回退机制由 A08 实施。A04 本地回退使用本批 `files-before/` 对照，仅撤销本批增量，保留 A02 及之前全部候选；没有线上变更可回退。
