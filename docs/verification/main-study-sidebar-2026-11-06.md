# 主站家庭入口与学科伴学：2026-11-06

> 后续更新：2026-11-07 已打通家庭档案、教材范围、理解工坊与原页。Compose 不变，代理热更新至 `assets/bridge-20261107/` 静态快照。下文“没有自动读取家庭资料”为初始版本历史状态；见 [资料互通验证](main-study-family-bridge-2026-11-07.md)。

已发布到 `https://172.19.116.53/` 的 Open WebUI 0.12.5 主站。用户要求左侧增加家庭学习入口，并让初一伴学项目借鉴前面讨论的开源项目；本次按 DeepTutor 与 OpenMAIC 落实设计参考。

## 用户可见变化

- 主站展开侧栏增加“家庭学习”“学科伴学”，收起侧栏显示相应图标；手机展开侧栏同样可用。
- “家庭学习”在新标签页打开 `/learning/auth/login`，保留主站草稿，沿用已有认证与档案，不重新绑定。
- “学科伴学”支持初一数学、语文、英语、道德与法治、历史、地理、生物。输入主题，可选填写出处与材料，预览学习请求后填入原生聊天框，用户自行编辑和发送；已有草稿时拒绝覆盖。
- “资料伴读”参考 DeepTutor 的资料范围和来源引用设计；“分步学习”参考 OpenMAIC 的分段课堂和学习输出设计。可以下载 Markdown 提纲并填写自己的学习卡。
- 页面内保留项目链接、许可证及设计参考说明。没有安装两套上游引擎，没有自动检索家庭资料或注册正式 Tool；没有宣称自动引用已核验、教师审核或正式判分。

来源固定版本和范围见 [SOURCES.md](../../deploy/open-webui-reuse/main-study/SOURCES.md)。JS/CSS 为独立编写，未复制上游代码或教材正文。聊天中的模型效果没有通过真实调用验证。

## 实现与发布

主站无本地前端源码；容器 `/app/build/index.html` 已提供 `/static/loader.js` 和 `/static/custom.css` 扩展槽。本次发布前两条公开资源均为 0 字节。HTTPS nginx 精确匹配这两个地址，以只读静态挂载提供本地 JS/CSS，`Cache-Control: no-store`。其他路由、Cookie/头隔离、TLS、原生页面及品牌保持原配置。

源码：`deploy/open-webui-reuse/main-study/study.js`、`study.css`、`SOURCES.md`。定位依据为实际 Open WebUI 0.12.5 的展开/收起侧栏和 ProseMirror `#chat-input`；版本升级后需复验 DOM 适配，若日后已有自定义 loader/CSS 应先合并，不直接覆盖。

新的当前 Compose：

`learning_data/deployments/family-math-20261105/compose-main-study-20261106.json`

从最新 `compose-study-workbench-20261106.json` 派生，严格比较只允许修改 proxy 配置路径和增加只读静态目录挂载。API/worker/gateway 镜像仍为 `sha256:16e21fac6e9942c6492d0a069650d5a9b3a94a4b6a6eb4ea35032b75855732c0`。

发布仅执行新 Compose 的 `up -d --no-deps --pull never learning-proxy`；proxy 容器重建，其余四个容器的 ID、镜像和启动时间逐一比对相同。没有重建数据卷、重绑、触碰正式 WebUI data、秘密、模型配置或历史聊天。旧 HTTP 53001 入口保留；本次增强只在指定 HTTPS 入口提供。

静态发布快照：`learning_data/deployments/family-math-20261105/main-study-20261106/`。

- JS SHA256：`77542a6063994f554830948034d3b3310c7178368afd2cabcebaa37d5ef07f84`
- CSS SHA256：`0d8a0aed5c1120df05a04486e07c82edff35cb02e1e70c2d0a5d54eab45ddc31`

## 验证

`scripts/probe_main_study.py` 用实际主站 HTML/构建资源、全新浏览器上下文和合成用户/模型进行验证。所有 API、socket、写请求被浏览器探针拦截；主站自动发出的 timezone POST 也被阻止，未访问真实账号或聊天。

1280px 与 390px 在候选及发布后均通过，发布后静态资源从真实 HTTPS 代理获取并核对 SHA256：

- 家庭链接目标和新标签页；侧栏展开/收起、刷新、原生“新对话”切换后不重复。
- 七学科、两学习方式、来源提示、材料按纯文本处理、Markdown 下载。
- 原生编辑器填入后发送按钮启用，表明编辑状态同步；不点击发送、不调用模型；已有草稿保留。
- Esc 关闭、手机无水平溢出、浏览器 pageerror 为 0。
- 主站公开 HTML 和静态资源 HTTP 200；家庭入口未登录时正确 303 至 `/auth?redirect=/learning/auth/login`；旧 53001 HTTP 200。
- nginx 部署后 `-t` 成功且返回 0，家庭 API healthy。部署前临时 nginx 校验输出成功但 Compose run 返回 130，未以该退出码宣称检查正常；部署后对实际运行配置的校验明确通过。

初次探针发现紧凑侧栏父元素会处理子元素 click，已阻止新增导航点击冒泡。截图复核又发现展开侧栏与紧凑侧栏共用 navigation 标识，已增加结构判别，避免在展开底部重复注入紧凑图标；增加对应断言并复验。后续收紧截图稳定性检查时，发现探针在恢复展开偏好后重复切换侧栏；修正探针后实际资源复验通过。

证据目录：`learning_data/verification/main-study-20261106/`，含 `prepared.json`、`deployed.json`、`browser-preview.json`、`browser-deployed.json`、桌面/手机截图；失败探针记录保留。没有将这些合成验证描述为真实家长已操作或真实模型教学效果验收。

本次没有读取学生记录，未重统计题数/作答；沿用前轮家庭服务的数据验收。只读 Goal API 返回 null；没有 Goal 写操作，没有 commit/push。

## 运维与回退

后续操作以新 Compose 为准，不用旧 Compose 执行整栈覆盖。变更仅在代理层，如需撤回入口，可将快照中的 `nginx.before.conf` 内容**原位写入**该快照的 `nginx.conf`，先在 proxy 内执行 `nginx -t -c /etc/nginx/dd-learning.conf`，通过后 `nginx -s reload -c /etc/nginx/dd-learning.conf`。这不需要回退家庭 API、数据库或数据卷；不要原子替换已被单文件 bind mount 的配置 inode。此回退说明未执行。
