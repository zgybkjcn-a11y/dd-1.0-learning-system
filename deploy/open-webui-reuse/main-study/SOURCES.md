# 主站学科伴学来源

本目录 JavaScript/CSS 为本项目独立编写。主站复用现有学习服务：题目中有明确署名的开源改编数据；概念和先修参考使用受限的本地映射。各项目的采用范围分别如下，不能把设计借鉴与数据改编混为一谈。

| 参考 | 固定版本 / 许可 | 实际采用 |
| --- | --- | --- |
| [xiaoyang111222/cn-math-taxonomy](https://github.com/xiaoyang111222/cn-math-taxonomy/tree/cf73951cf4b5d2bdbc8a75bb9cb9e961e55277ab) | cf73951cf4b5d2bdbc8a75bb9cb9e961e55277ab / 数据 CC BY-NC 4.0 | 已有题库 29 道改编题，逐题保留作者、上游 ID、固定链接、许可、修改说明；主站按知识点和难度展示已映射的关联题，转家庭页正常练习 |
| [dangjian/faststudy-knowledge](https://github.com/dangjian/faststudy-knowledge/tree/508748a2c8dddc1253100b2d10d91c9526903f67) | 508748a2c8dddc1253100b2d10d91c9526903f67 / 代码 MIT、图谱 CC BY-NC-SA 4.0 | 参考书→章→概念→先修→原页结构，主站展示本地 20 题—18 概念映射及有界先修链；教材版本和页码另行核对；不复制教材正文，仓库本身不含题库 |
| [HKUDS/DeepTutor](https://github.com/HKUDS/DeepTutor/tree/60fb3bdfddb30b7740c7ce3bd9b28d908f2af6db) | 60fb3bdfddb30b7740c7ce3bd9b28d908f2af6db / Apache-2.0 | 资料范围、原文依据、区分引用和推理；新增有编号的参考卡、课堂出处栏和点击原页核对；没有运行 RAG/PageIndex 引擎 |
| [THU-MAIC/OpenMAIC](https://github.com/THU-MAIC/OpenMAIC/tree/5bd8cc840ee6397d063e1fe6aba974b9f0401593) | 5bd8cc840ee6397d063e1fe6aba974b9f0401593 / MIT | 四步课堂、可选知识点、局部数学参数演示、可断网播放的单文件 HTML；没有运行课堂生成代理 |

README/LICENSE 证据复用 `learning_data/verification/scenarios-integration-20261106/`。项目线索来自 faststudy-knowledge 的 SCENARIOS（508748a2c8dddc1253100b2d10d91c9526903f67）。

2026-11-07 后续深化：DeepTutor README 的 grounded reading/source-linked citations，OpenMAIC README 的 rich scene types/offline HTML export 是本地设计依据。课堂由当前 `study-support` 公开参考确定性组装，四步为明确目标、观察理解、自己解释、回顾核对。没有调用生成模型，没有自动判分或掌握度声明。

主站和离线 HTML 共用同一渲染函数。导出只包含明确投影的公开教材元数据、知识参考和阅读步骤，不含面板手输内容、档案信息、学生资料、教材图片或运行凭证。离线无 CDN、网络请求、模型或存储依赖；非数学及未映射范围标注为阅读活动课堂。数轴只用于七上加/减概念，二上第二单元只演示乘法，等式/方程范围不混用数轴。

未连接时支持七年级数学、语文、英语、道德与法治、历史、地理、生物；连接家庭后按服务端当前档案提供二年级三科或七年级七科。这里是学习请求辅助，不是经教师审核的学科内容库。填入聊天框后由用户自行编辑、发送，实际聊天仍使用原有模型配置。未调用模型验证教学效果。

2026-11-07 家庭资料打通：复用现有同源浏览器会话和学习 API，只读取当前档案、教材目录、理解工坊公开参考及教材原图。所有参考请求绑定服务端档案 revision，展示前后及填入/导出前再次核对；不读取令牌、作答、成绩或历史聊天。提示词投影只包括公开课本/章节/概念/阅读步骤，排除档案姓名、账号和学生标识；教材图像仅用于本地阅读，未自动发送给模型。

家庭页 bridge 只在本浏览器 localStorage 写入按账号、档案、revision 分隔的课本/章节选择与时间戳；不存储学生作答或姓名，跨设备共享的仅是既有服务端档案选择，课本/章节同步限同一浏览器。主站回到家庭页采用带 revision 的章节链接，由用户点击原有切章流程，保留未完成题目确认。

家庭入口复用 `/learning/auth/login`，新标签页保留聊天草稿。正式 Tools 注册仍独立于本入口，未借本次导航变更写入正式 WebUI data。DeepTutor/OpenMAIC 仍为设计参考，未安装其引擎。

2026-11-07 用户明确指定的两项目接入：新增“知识路线与关联练习”，通过现有只读 `/math-references` 接口查询；读取前绑定当前档案 revision，读取后复查身份，换书/章/档案取消旧请求并清空结果。先修关系只是回顾建议，不诊断错因或声称掌握。主站不读取作答历史或 `/question-choices`。

练习跳转只传公开的书、章、题目版本 ID 和 revision；家庭页从其正常加载的当前题目目录重新验证，并要求点击“开始这道关联题”，调用原有切章和启动处理函数，保留未完成题确认。链接打开本身不创建测验或提交答案。无新增题目、OCR、服务端/数据库/向量库变更或模型调用。

许可、原始来源与本地改编材料保留于 `learning_service/data/NOTICE.md`、`cn-math-taxonomy-LICENSE.txt`、`faststudy-NOTICE.txt`、`faststudy-LICENSE-DATA.txt`；20题映射与18概念见 `family_concepts_v1.json`。本次仅家庭非商业使用；本地内容核对不等同于教师签署审核，其他学科尚无这两个项目的精确映射。

2026-11-07 主站原生聊天接入：新增聊天框旁的学科助手/教材检索/分步讲解/检查思路/关联练习快捷入口。使用 Open WebUI 原生 `?tools=dd_family_study_readonly_v1` 新聊天参数选择独立只读工具，保留当前草稿，不自动发送。工具源码位于上一级 `readonly_study_tools.py`，仅六个公开查询方法，沿用当前请求的宿主身份与家庭 Cookie；不向模型返回登录信息或个人记录，不需要新增管理员密钥。

原页链接包含当前书章、页码和上下文版本，家庭页复核后由用户打开对应原页。聊天出处卡中的概念说明标为本地参考，教材检索只提供原页位置/标题，不把未经全文核验的提取文字当作教材原句或标准答案。当前仍为家庭非商业使用，两个项目的版本/许可及数学映射边界保持。
