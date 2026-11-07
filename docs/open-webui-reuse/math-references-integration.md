# 家庭数学参考接入学习服务与 Open WebUI Tools

2026-11-06。适配器 1.2.0，目标 Open WebUI 0.12.5，数据库 schema 11，不需要数据迁移。

当前新学习API与家庭工作台“理解工坊”已经上线，部署及数据保留证据见[当前验证](../verification/study-workbench-2026-11-06.md)。正式Open WebUI Tools尚未注册；下述导入步骤仍供管理员使用。

学习服务新增只读 `GET /api/v1/math-references`。Open WebUI 的薄适配器新增三个方法；仍只需导入 `learning_service/tools.py` 一个源码文件，数学逻辑和资料留在独立学习服务。

| 方法 | 模型可传参数 | 用途 |
| --- | --- | --- |
| `get_math_scope` | `book_id`、`chapter_id`，均可空 | 查看当前档案数学课本/章节的本地概念与已核验题目编号 |
| `get_math_question_reference` | 必填 `question_version_id`，可选书/章 | 查看指定题的概念、两层以内先修参考、同章最多三道相关题编号 |
| `get_math_concept_reference` | 必填 `concept_id`，可选书/章 | 查看一个概念的本地说明、可能核对点和先修参考 |

留空课本默认当前档案数学上册；留空章节为整本书。年级和学习者由学习服务决定，模型不能传账号、学习者或上下文版本。先在工作台选择档案；Tools 在查询前后固定核对共享选择与版本，接口本身也检查查询期间的切换。切换后返回 `LEARNER_CONTEXT_CHANGED`，不返回旧档案结果。

返回的是参考资料：`reference_only=true`、`eligible_as_grading_basis=false`、`teacher_reviewed=false`、`mastery_claim=null`。可能核对点不代表已确认的错误原因。题干、答案、原始作答、账号字段和任意上游附加字段不进入 Tools 输出。原页仅给页码、PDF 哈希及相对图片路径；在已有登录工作台阅读原图，不携带访问凭证到聊天。

首批冻结 20 道现有应用题的映射、18 个本地概念/核对点。覆盖二上第二/三/五单元、七上第二/五章；整本书查询也只返回这个小样本。未配映射的题和章节明确返回 `unmapped`，不改用其他版本。七下尚未映射；二下数学 OCR 尚未通过整书双重审核，不加入本接口。

参考资料、题库原文件、已批准共享题目的完整版本指纹以及原 PDF 均绑定 SHA256。数据库题干、提示、答案、单位、解析或 validator 变化会使相关映射失效；变式不继承 v1 的旧映射。题目撤回后不再展示。此功能不创建题目、判分、改阶段、创建任务或写入向量库，不调用模型/OCR。查询参数只接受固定名单，重复参数也拒绝。

`faststudy-knowledge` 固定 commit `508748a2c8dddc1253100b2d10d91c9526903f67` 提供结构参考：书→章→概念→先修关系→出处。其示例为北师大版；本地人教版说明和页码另行核对，未复制出版社教材转写。图谱相关元数据保留 CC BY-NC-SA 4.0 说明与 NOTICE；未引入其 MIT 代码。原有改编题来自 `cn-math-taxonomy`，保留 CC BY-NC 4.0 和固定 commit 的来源信息。商业复用需要另行处理这些非商业许可。

## 导入与配置

1. 使用新候选包中的完整 `learning_service/tools.py` 导入一个新 Tool，或由管理员审阅后更新既有适配器。总计 15 个公开方法，另包含[学科阅读辅助](scenarios-adoption.md)的 `get_study_support`。不要直接将全量 OpenAPI 注册给模型。
2. 沿用当前学习服务的内部地址、adapter secret 和**已有绑定的 issuer**。真实多用户设置 `DD_TRUSTED_SUBJECT=""`，身份来自宿主注入 `__user__`；`DD_SHARED_LEARNER_CONTEXT=true`；UserValves 的学习者字段留空以跟随工作台选择。不需要重绑账号。
3. 先部署候选学习服务模块/参考 JSON/NOTICE，并保留当前 PDF 的只读挂载和现有数据卷。只注册 Tools 而不部署新 API 会返回服务错误，不能视为接入完成。含工作台入口的最新 source profile 是 `reuse-runtime-study-workbench-v1`；历史 `reuse-runtime-math-references-v1`、practice/textbook/profile 候选仍可验证。
4. 先手动调用三个读方法验证；真实模型聊天、共享给其他用户、外发学生资料及模型预算仍按用户授权处理。本次验证使用合成身份和本机公共教材，没有真实模型调用。

可核对示例：二年级选择第三单元后调用 `get_math_scope(chapter_id="3")`；再查询 `family-word-g2-share-1-v1` 或概念 `g2-share`。七年级选择第五章后查询 `g7-solve`，先修应为等式性质 `g7-equality`，不把后续代回检验列成解方程的先修。

源码完成与正式注册是两项状态。用户要求不读取/修改正式 WebUI data，因而本次候选及隔离验证不写入正式 Tool 记录；正式启用需要管理员在 UI 导入，并按当前部署配置发布新学习 API。完整证据见 `docs/verification/math-reference-tools-2026-11-06.md`。
