# 主站采用 cn-math-taxonomy 与 faststudy-knowledge（2026-11-07）

2026-11-07 已上线。本轮按用户明确指定的两个项目，把现有家庭学习数据接入主站“学科伴学 → 知识路线与关联练习”。先选择课本/章节（章节可选），再选知识点，查看先修关系、本地解释、核对点和当前人教版原页；按难度选择关联题，进入家庭页后明确点击“开始这道关联题”。

## 具体采用

| 项目 | 已有材料与本轮使用 |
| --- | --- |
| [cn-math-taxonomy](https://github.com/xiaoyang111222/cn-math-taxonomy/tree/cf73951cf4b5d2bdbc8a75bb9cb9e961e55277ab) | 固定 commit `cf73951cf4b5d2bdbc8a75bb9cb9e961e55277ab`，数据 CC BY-NC 4.0。家庭题库原有 29 道改编题，本轮主站显示其中已经建立概念映射的关联题，保留署名、上游 ID/固定链接、许可和修改说明；另有本地编写题，分别标注。 |
| [faststudy-knowledge](https://github.com/dangjian/faststudy-knowledge/tree/508748a2c8dddc1253100b2d10d91c9526903f67) | 固定 commit `508748a2c8dddc1253100b2d10d91c9526903f67`，代码 MIT、图谱 CC BY-NC-SA 4.0，教材版权归出版社。沿用已建立的 20题—18概念本地映射，参考书→章→概念→先修→出处组织方式；本轮在主站展示有界先修关系与精确关联题。上游数学示例为北师大版，本地人教版章节/页码另行核对；上游不含题库。 |

本轮没有新增题目，仍为 74 道；精确概念映射只覆盖其中 20 道，涉及二上第二/三/五单元、七上第二/五章的局部内容。其他学科和未映射章节继续提供现有阅读活动，明确显示暂无精确数学映射。先修关系为回顾参考，hard/soft 分别标为基础回顾/辅助联系，不将题目答对当作掌握度，也不直接诊断错误原因。本地语义核对与算术复算不是教师签署审核。

完整来源见 [主站 SOURCES](../../deploy/open-webui-reuse/main-study/SOURCES.md) 和 `learning_service/data/NOTICE.md`、两项目许可文件。JavaScript/CSS 为本地实现，无上游引擎安装或教材正文复制，当前为家庭非商业使用。

## 接口与跨页行为

主站只新增使用现有只读 `/learning/api/v1/math-references`，按 `book_id/chapter_id/concept_id` 查询；不调用 `/question-choices` 或读取作答历史。服务端继续校验当前档案权限、题库指纹与 PDF 版本；客户端绑定档案 revision 和书章范围，读取后复查身份，换范围时中止/丢弃旧请求并清空旧链接。图文通过 textContent 和现有受限原页接口展示，未发送到模型。

关联练习链接只携带公开书/章/题目版本 ID 和 revision。家庭页从正常加载的当前题目目录复核对应关系，打开链接本身不会创建测验。用户点击按钮后调用原有 `selectLearningScope` / `launchGameChoice`，未完成题的换题或切章确认保留；取消切章不得继续启动。过期 revision、跨年级、错误书章或未知题拒绝。入口放在家庭工作区各视图共享的位置，恢复到答题页时也可看到。

## 验证与部署

验证采用临时数据库、合成家庭身份、实际家庭 API/网关/HTML 与公开 PDF，不使用真实学生数据或真实模型。`tests/test_main_study_bridge.py` 在桌面 1280px / 手机 390px 检查：

- 主站选择概念→先修关系/核对点→原页→按难度筛选关联题，区分上游改编与本地编写。
- 打开关联链接不创建测验；点击才启动指定冻结题；同章换题、跨章切换均保留未完成题确认，拒绝后不启动。
- 过期 revision、跨年级题拒绝；非数学和未映射章节无旧题链接；二年级与七年级隔离。
- 迟到的概念响应不覆盖新章节；档案切换清空旧参考；前章基础原页可查看。
- 原有分步课堂、离线 HTML、聊天草稿保留、身份失效禁止导出、手机布局继续回归。

首次联调发现恢复到答题页时，原首页区域内的关联入口不可见，已移到工作区共享区域。另纠正了测试对 `g2-share` 必有先修的错误假设：现有映射没有这条边，验证前章基础改用明确有边的 `g2-small-table`，没有为了测试虚构关系。原生 WebUI 公开构建资源加载首次超过探针的 15 秒导航上限，导航等待单独提高至 60 秒，控件断言仍为 15 秒。

完整浏览器流程 **2 项通过，174.22 秒**，见 `browser-tests-r3.log` 与 `browser/bridge-{1280,390}.json`。两视口页面脚本错误均为 0，临时库作答记录和 provider_calls 均为 0；合成环境仅显式启动/切换练习会创建测验。截图见 `browser/knowledge-route-{1280,390}.png` 与 `browser/linked-practice-{1280,390}.png`。

实际 Open WebUI 0.12.5 前端构建资源的候选与发布后探针在桌面/手机均通过（`native-candidate-r2.log`、`native-deployed.log`），模型调用 0；所有 API 使用合成响应，宿主的自动时区写请求被拦截。没有把该探针描述为真实家长或真实模型的教学效果验收。证据目录：`learning_data/verification/main-study-knowledge-20261107/`。

## 当前发布

Compose 保持 `learning_data/deployments/family-math-20261105/compose-main-study-20261106.json`，家庭 API/worker/gateway 镜像保持 `sha256:16e21fac6e9942c6492d0a069650d5a9b3a94a4b6a6eb4ea35032b75855732c0`。

静态快照更新为 `learning_data/deployments/family-math-20261105/main-study-20261106/assets/knowledge-20261107/`。新脚本 `scripts/prepare_main_study_knowledge.py` 以当前 classroom 版本为基线，断言只替换三条静态 alias，候选/实际 nginx 配置验证通过后热 reload。五容器 ID、镜像、启动时间完全保持，API healthy，无容器或卷重建。部署证据为 `deployment/prepared.json`、`applied.json`、前后 nginx 配置与 `public-assets.json`。

实际 HTTPS 三个资源均为 200 / no-store，与本次已测源码逐字节一致：

- study.js：`afd423824d9fdb822f95360b716f2766f720098f50cb83e8fef2e27c3ad08dfa`
- study.css：`a4137c06d5c57d3857f0b1fcfdaa88c969bf21904fa42b8cd53a03df5d67fad7`
- family-bridge.js：`aa25272f0c8322d2b4549a70466a19d8c1f2eb3fe57f113bff914a1fb896ec77`

保存正在填写的内容后，刷新主站与家庭页即可使用。回退时仅原位恢复本轮 `deployment/nginx.before.conf` 并 nginx 校验/reload；不要用旧 Compose 覆盖整栈。


持续约束：保留所有未提交改动；不读改根 Compose、正式 WebUI data/秘密或无关聊天账号；不重绑/重建卷；不调用真实模型或外部 OCR、不写向量库或 Goal。二下教材逐页双重审核门槛保持。
