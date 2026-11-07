# 学科伴学与家庭学习资料打通

> 后续已上线四步课堂、编号参考卡和离线 HTML，静态快照为 `assets/classroom-20261107/`，三条静态 alias 更新；家庭互通、Compose 和服务镜像保持。下文 bridge 静态哈希为上一版，详见 [当前课堂版本](main-study-classroom-2026-11-07.md)。

2026-11-07 已发布。主站“学科伴学”现在通过现有家庭会话读取当前档案、教材目录、理解工坊参考和原页，不再只提供家庭页跳转。

## 可以使用的功能

- 打开伴学自动连接已有家庭会话；未选档案时引导在家庭学习选择，未登录时可进入既有登录流程，无需重绑。
- 当前档案决定年级与开课科目：二年级三科、七年级七科。可选课本和章节，章节可留空表示整本书。
- 同一浏览器中，刷新后的家庭页更换课本或章节，伴学会重新读取同一范围。共享选择只包含课本 ID、章节 ID、时间戳，按账号、档案及服务端 revision 隔离。跨设备不共享书章选择。
- 伴学可展示学习步骤、已有数学知识卡及局部出处；可直接阅读原页、翻页和点击放大。非数学仍为阅读步骤，没有伪装为完整逐章知识库。
- “将公开学习参考带入请求”可以取消勾选；实际内容在预览中可见。只带入课本、章节、阅读步骤、概念与页码参考，不带档案姓名、账号/学生 ID、作答或成绩。原页图片只在本地浏览，不自动发送给模型。
- “打开家庭学习 / 切换档案”携带当前书章与 revision；家庭页显示“打开伴学所选章节”，点击后走原有范围切换流程，保留未完成题目的确认。
- 已有聊天草稿不覆盖。填入后仍需用户自行发送，未自动调用模型。当前实现是教材与理解工坊资料互通，不将历史聊天写成学习成绩。

初次使用需刷新主站和已打开的家庭页面，以加载两侧新脚本。若浏览器仍有旧静态缓存，主站使用 Ctrl+F5。

## 身份与范围核对

主站只调用现有同源 GET：`auth/session`、`learners`、`textbooks`、`study-support`、指定教材页图片。网关继续核对 WebUI Cookie 和家庭会话身份一致性，主站不读取令牌、设置永久密钥或伪造学习者头。

每次读取都携带服务端 `X-Learner-Context-Version`，取得目录/参考后再次检查会话。加载用 AbortController 和 generation 序号淘汰迟到响应；填入、导出及图片显示前再次检查身份/档案。面板可见时定期核对，切回页面也重新同步。变化或失效后清空参考与面板里的旧输入并阻止导出；已经进入聊天框的用户草稿保留。

原有 API 仍决定可访问范围，本地保存的书章选择不作为权限依据。参考仍保留 `reference_only`、未教师审核、不能作为判分依据的边界。

## 部署

当前 Compose 仍为 `learning_data/deployments/family-math-20261105/compose-main-study-20261106.json`。

静态快照位于现有只读挂载内的 `main-study-20261106/assets/bridge-20261107/`。代理把原生 loader/custom.css 路径指向新快照；仅对 `/learning/ui` HTML 在闭合 body 前插入 family-bridge 脚本，登录页、JSON API 和主站不插入该脚本。

准备与发布脚本：`scripts/prepare_main_study_bridge.py`。候选配置校验后，原位更新已挂载配置并 nginx reload。五个容器 ID、镜像、启动时间全部保持；未重建容器或卷、未重绑、未改服务端源码/schema、未访问正式 WebUI data 或环境秘密。

API/worker/gateway 镜像保持 `sha256:16e21fac6e9942c6492d0a069650d5a9b3a94a4b6a6eb4ea35032b75855732c0`。

线上公开资源逐项校验：

| 文件 | SHA256 |
| --- | --- |
| study.js | c7dbc105b1f99f2d3d381225ef652c702ad4ed3c879ce1bafd7dd991b367ab3a |
| study.css | a72c1d7f37a925bafab85a5bcb11ae9881b5abcacf2ff181005d7edcc5a657ca |
| family-bridge.js | 132c677238e73c69f550ea9f2354f51e2a4d32947f805f048415a4b1b4550e19 |

三项均 HTTP 200、`Cache-Control: no-store`。正式 Tools 注册仍未执行；DeepTutor/OpenMAIC 仍为设计借鉴，没有新增上游引擎或模型调用。

## 验证与证据

- `tests/test_main_study_bridge.py`：1280px/390px **2 项通过**。真实家庭 FastAPI/网关实现、实际家庭 HTML、临时数据库、合成身份和公开教材 PDF；覆盖无档案提示、跨标签书章同步、数学原页翻页、历史阅读步骤、公开资料预览/下载、返回同一章节、七年级→二年级切换时迟到响应丢弃、草稿保留、身份失效阻止导出。作答 0、provider_calls 0。
- 原生主站构建资源浏览器探针：桌面/手机候选和发布后均通过。使用合成 API，真实模型、聊天保存和账号 timezone 写入全部拦截；验证主站原生编辑器及原有导航兼容性。没有读取真实账号或聊天。
- 与生产相同 nginx 镜像的 `--network none` 临时容器验证实际 HTML 过滤行为：仅 `/learning/ui` 插入一次；登录页、JSON API、主站为零次。合成上游，未挂任何正式 data/秘密；临时容器已移除。
- JavaScript 语法与 Python 编译通过；正式 proxy 配置 nginx `-t` 通过，家庭 API healthy。

早期测试发现合成主站缺少 UTF-8 声明、导航盒模型在无 Tailwind 的宿主中溢出，以及竞态测试延迟挂在前一个自动同步请求上的问题；已修正，最终两视口复验通过。未把这些合成测试描述为真实家长已验收，也未真实调用模型测试教学效果。

证据：`learning_data/verification/main-study-bridge-20261107/`，含两视口报告/截图、native-deployed 浏览器报告，以及 deployment 内的 before/candidate 配置、容器状态、静态哈希、应用记录和 nginx 运行验证。没有重统计真实学生记录；服务数据沿用前轮验收，没有 Goal 写操作或 git commit/push。

若需回退，只将本次 `deployment/nginx.before.conf` 原位写回当前挂载的 nginx 配置，校验后 reload；不要使用旧 Compose 整栈覆盖。新旧静态快照均保留。
