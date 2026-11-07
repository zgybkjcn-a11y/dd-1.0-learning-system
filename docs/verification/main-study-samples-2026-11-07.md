# 主站后续三个小样本（2026-11-07）

本轮先按恢复记录只读核对，再实现可逆候选和隔离验证。**三个样本尚未上线**；正式主站仍使用 `chat-20261107`，Compose、容器、Tool、绑定和数据保持。本报告不代表真实模型或教学效果验收。

## 恢复核对

已读取恢复指令、最新总交接、教材约定及主站聊天/课堂/知识路线验证。`main...origin/main` 上原有未提交改动全部保留，初始状态保存在证据目录 `git-status.before.txt`。五容器运行，Open WebUI/API healthy，主站返回 200。三份静态源码与交接公布哈希一致，nginx 三条 alias 指向 `chat-20261107`。只读 `get_goal` 返回 null，没有调用 Goal 写 API。

## 候选行为

| 小样本 | 入口与行为 | 范围 |
| --- | --- | --- |
| 等式性质交互演示 | 学科伴学 → 七上数学第五章 → 分步课堂 → 等式的基本性质 → 观察理解。先预测，再操作；从 6 = 6 出发调节 −6～6，两边同加与只改左边对比 | 已有等式性质先修卡，第 116 页；仅加法性质，不涵盖乘除变形；零的例外单独说明 |
| 可视化知识路线 | 原“知识路线与关联练习”上方绘制 Mermaid 图，节点支持点击/键盘定位现有参考卡，继续打开原页或选择关联题 | 只画服务返回的边；实线基础回顾、虚线辅助联系；没有关系时保留孤立节点，不补造全章图 |
| 章节复习 PDF | 七上数学第五章启用“章节复习 / PDF”，预览三页、通过浏览器“打印 / 另存为 PDF”，也可下载离线打印稿 | 等式性质与解方程两个已有参考卡；本地例子 x + 3 = 9；原页书内 116、120、128 页；不是完整章节或正式测试卷 |

等式性质原本只在先修参考中，课堂只列直接关联概念，首轮测试发现无法选择。本次把当前书章已返回的该条参考加入课堂选择，未新增概念或关系；二年级、其他书章不显示此演示。复习 PDF 按性质→求解的顺序组织。

在线和离线课堂复用同一渲染函数。PDF 预览、离线打印稿与隔离打印 iframe 使用同一公开投影；打印前重新校验家庭身份，正文不含姓名、账号、档案 ID、revision、面板手输内容或教材图片。iframe 只装入公开卡片，不打印宿主聊天/档案。换范围或身份失效时清空图、课堂、复习预览和打印 iframe；关闭预览会取消尚未执行的打印。

Mermaid 固定为 11.12.1，核对官方 npm 来源、包完整性、MIT 正文及其 67 个实际打包依赖版本的许可全文。只使用固定本地资源，SRI、strict、受限图标签；渲染失败时保留原有文字卡片。SVG 演示和打印模板为本地实现，没有引入 JSXGraph/Marp 或新的教学平台。详见 [SOURCES](../../deploy/open-webui-reuse/main-study/SOURCES.md) 与其 vendor 目录。

## 验证证据

证据根目录：`learning_data/verification/main-study-samples-20261107/`。测试只用合成身份、临时数据库、现有公开参考 PDF 和实际候选静态资源；不读正式 WebUI data，不发真实模型/embedding 请求。

- `browser-tests-r1.log`：发现已有等式先修卡未出现在课堂选择，已修复。
- `browser-tests-r2.log`：演示参数组合通过，打印测试的 window load 捕获无法捕获 iframe load，已把测试桩改为在 iframe 元素上捕获；独立复现确认实际打印函数已被调用。
- `print-smoke.pdf`：早期三页实物检查，供排查留存；最终产物以 `browser/` 为准。
- `native-candidate.log`：实际 Open WebUI 0.12.5 前端资源、合成且拦截的 API，桌面 1280/手机 390 通过；原生编辑器、工具菜单和草稿保持，页面错误 0、模型调用 0。之后仅调整复习卡顺序、关闭预览取消打印等局部行为，最终完整桥接测试覆盖。
- `browser-tests-r3.log`：桌面 1280/手机 390 **2 项完整流程通过，298.86 秒**。每个视口 26 组等式操作（两种模式 × −6～6）、先预测门槛、零/负数/预测不符、已有原页出处与离线交互均通过；图中基础回顾与辅助联系分开验证，无关系节点保留空缺。原有跨书章/档案竞态、关联练习显式启动、草稿保留、身份失效禁用、二年级乘法和历史阅读课堂继续通过。临时数据库作答记录和 provider_calls 均为 0，页面错误 0。
- `browser/chapter-review-{1280,390}.pdf`：两视口分别实际生成 3 页；检查中文、公式、书内页码、链接和 A4 边距，无裁切。三个 `review-page-*.png` 已逐页查看。`samples-*.json` 保存参数组合与 PDF 来源链接。
- 隔离打印 iframe 检查为 3 张公开卡片，离线 HTML/PDF 均排除手输测试标记和身份字段；离线课堂与打印稿的 HTTP/HTTPS 请求为 0。原生打印对话框由测试桩替代，PDF 则实际调用 Chromium 打印引擎生成；不声称已在家长的具体浏览器/打印机上验收。
- `candidate/nginx-isolated.json`：使用与线上一致的固定 nginx 镜像，在无网络、无宿主端口、无正式挂载的临时容器内检查。临时自签名证书，未读取正式证书/秘密。候选 nginx 语法通过；四条本机 HTTPS 静态路由均 200/no-store、MIME 和文件哈希正确，临时容器已移除。
- JavaScript/Python 语法检查、`git diff --check` 通过；初始 git status 的全部条目保留，候选快照与最终源码哈希一致，活动 nginx 配置和 `family-bridge.js` 未变。
- `final-readonly-status.json`：结束前只读核对五容器仍运行，WebUI/API healthy；匿名 HTTPS 读取三份线上静态资源，仍逐字节匹配本轮开始时的 `chat-20261107` 原文件。没有发布候选、调用真实模型、写 Goal、重复注册 Tool、重绑、重建卷或提交/推送。

## 候选交付与继续方式

源码为 `deploy/open-webui-reuse/main-study/study.js`、`study.css` 和新增 `vendor/`；`family-bridge.js` 与六方法 Tool 保持原哈希。没有后端、题库、教材索引或服务镜像变更。

`scripts/prepare_main_study_samples.py` 仅在证据目录生成静态快照、哈希清单和 nginx 候选，不调用 Docker 或写活动配置。候选配置限定为替换现有三条静态 alias，另增一条本机 Mermaid 渲染资源路由；Compose、认证、代理 API、Cookie、网络与数据挂载不变。正式发布尚未执行，不能把本地文件或候选配置当作已上线证据。

最终候选 `study.js` SHA-256：`fe26d4d4ae6834944fd093d9954808b118b7706daeb1aa42df459090cf75518d`；`study.css`：`952fddccb9e5366d350b0bd9bebf88fe76ebeea6861bed9b6d9fa7e697af292a`。静态快照在 `candidate/samples-20261107/`，用于后续评审；与本报告中的测试结果对应。

可直接体验的实物：

- [离线等式课堂](../../learning_data/verification/main-study-samples-20261107/browser/equality-classroom-1280.html)：打开后选“等式的基本性质”，进入“观察理解”。
- [知识路线截图](../../learning_data/verification/main-study-samples-20261107/browser/route-sample-1280.png)；交互入口在主站候选中，截图本身不具有点击能力。
- [三页复习 PDF](../../learning_data/verification/main-study-samples-20261107/browser/chapter-review-1280.pdf) 与 [离线打印稿](../../learning_data/verification/main-study-samples-20261107/browser/chapter-review-1280.html)。

下一步先体验离线等式课堂和三页复习 PDF，再依据反馈决定是否发布这组静态候选。已有六方法 Tool 无需重新注册，仍无需重绑；真实聊天效果等待家长自行使用已有模型反馈。教材 OCR 仍是 106 页已识别、完整页双重审核通过 0，不涉及本轮候选。
