# 主站 DeepTutor / OpenMAIC 设计采用深化

2026-11-07 已上线。用户要求“初一 AI 智慧伴学”继续借鉴两个开源项目；本次在既有资料打通基础上，增加可操作的四步课堂、编号参考卡和单文件离线课堂。

## 开源项目与实际采用

| 项目与固定版本 | 核对依据 | 主站实际行为 |
| --- | --- | --- |
| DeepTutor，`60fb3bdfddb30b7740c7ce3bd9b28d908f2af6db`，Apache-2.0 | README grounded knowledge/reading、source-linked citations、PageIndex page-level citations | 知识卡显示 `[参考 n]`，区分本地讲解、综合核对点、教材页码；课堂出处栏可点击原页核对；预览提示词要求引用已给出的参考编号，不补造页码或冒充教材原句 |
| OpenMAIC，`5bd8cc840ee6397d063e1fe6aba974b9f0401593`，MIT | README rich scene types、outline→scene、offline HTML export | 可选择当前范围内的知识点，按明确目标→观察理解→自己解释→回顾核对推进；配合局部数学交互演示；导出同一渲染器的单文件 HTML，可断网使用 |

README/LICENSE 实物沿用 `learning_data/verification/scenarios-integration-20261106/`。JavaScript/CSS 独立编写，没有复制这两个项目的实现代码或安装其运行引擎。页面和离线文件保留项目、固定版本链接及许可说明。整体采用范围见 [SOURCES.md](../../deploy/open-webui-reuse/main-study/SOURCES.md)。

## 使用路径与边界

主站刷新后：左侧 **学科伴学 → 选择家庭档案对应的课本/章节 → 开始分步课堂**，或 **下载离线课堂**。需已有家庭会话；两项按钮在未连接、读取中或档案失效时禁用。

课堂内容确定性组装自当前 `study-support`，不触发模型生成：

- 数学只使用已有局部知识卡；有理数加/减卡支持改变起点、变化量及加减运算的数轴演示。整式、方程等无匹配演示时不混入数轴。
- 二年级已有对应知识卡支持同组数量图；二上第二单元只演示乘法，除法仅在服务允许的后续范围出现。
- 非数学/未映射范围为结合当前课本的阅读活动课堂，明确没有该章已核验知识讲解或精确页码映射。
- 课堂“回顾核对”复选框只是本次自查，不存储成绩、不算掌握度，也不添加题目、作答或判分记录。
- 课堂和教材原页仍受现有会话/revision 核对，家长切换档案后旧课堂清空。下载前复验身份。

离线导出只包括明确投影的公开课本/章节/版本信息、知识卡、检查点与阅读步骤；不含面板手输主题/疑问、姓名、账号/学生 ID、学生资料、作答、教材图片、凭证。采用安全 JSON 嵌入（`<` 转义）、DOM textContent 和 CSP，无 CDN、API、模型或存储依赖。在线与离线同一渲染函数；离线原页位置为文字，需对照手边课本。没有生成 PPTX、语音或多代理课堂。

## 验证

`tests/test_main_study_bridge.py` 扩展为完整主站/家庭互通加课堂流程，1280px/390px **2 项通过**（143.94 秒）。使用临时数据库、合成身份、实际家庭 API/网关/HTML 和公开 PDF，主站课堂为实际候选 JS/CSS：

- 课堂知识点选择、四步骤、回顾勾选、边界按钮状态、原页打开。
- 有理数 `−3 − (−5) = 2`；二上第二单元 `3 × 4 = 12`、修改为 `2 × 4 = 8` 且图中 8 个点，不出现除法。
- 历史只提供阅读活动，知识点选择禁用、不出现数学演示。
- 离线 HTML 在浏览器 offline 模式下成功操作，HTTP/HTTPS 请求 0；手输的 `PRIVATE_STUDENT_TEXT <script>…`、档案 ID、合成身份不进入导出。
- 沿用书章跨标签同步、七年级→二年级迟到响应丢弃、草稿保留和身份失效阻止导出测试；新课堂入口亦随失效禁用。
- 临时作答记录 0、provider_calls 0、页面错误 0。

`scripts/probe_main_study.py` 的实际 Open WebUI 0.12.5 构建资源在桌面/手机候选与发布后通过原生导航、编辑器及草稿保留回归。该探针全部合成 API，不对真实账号/聊天发读写请求；课堂主体与家庭接口联调证据为前一项，不冒充真实家长或模型已验收。

截图与离线样例位于 `learning_data/verification/main-study-classroom-20261107/`，其中 `classroom-1280.html` 是公开参考样例；服务身份与 API 均为合成，示例无真实学生信息。

## 发布状态

Compose 保持 `learning_data/deployments/family-math-20261105/compose-main-study-20261106.json`。API/worker/gateway 仍使用 `sha256:16e21fac6e9942c6492d0a069650d5a9b3a94a4b6a6eb4ea35032b75855732c0`。

新静态快照：`learning_data/deployments/family-math-20261105/main-study-20261106/assets/classroom-20261107/`。

`scripts/prepare_main_study_classroom.py` 证明配置差异仅为现有三条静态 alias 目录从 bridge 更新到 classroom；认证、HTML 注入、API、Cookie、网络与数据挂载配置均保持。nginx 候选/实际配置校验通过后热 reload，五个容器 ID/镜像/启动时间一致，无容器或卷重建。

线上文件均 HTTP 200、no-store，SHA256：

- study.js：`2e8bbe60046c8707b19ea0365df8c409a5616c231af5e4b2c4ec4a9553eb8a56`
- study.css：`81c888ea6a850c571165c20d6c46a13c98339e107bcdf26e51da3ea5ea2f56e3`
- family-bridge.js：`132c677238e73c69f550ea9f2354f51e2a4d32947f805f048415a4b1b4550e19`（保持）

部署证据在该验证目录 `deployment/`：前后配置、容器状态、候选/应用记录和公开资源校验。若需回退，原位恢复本轮 `nginx.before.conf`，nginx 校验后 reload；保留所有旧快照，勿用旧 Compose 整栈覆盖。

未访问正式 WebUI data/秘密/无关账号或聊天，未注册正式 Tool，未调用真实模型/外部 OCR，未写生产向量或 Goal，未 commit/push。
