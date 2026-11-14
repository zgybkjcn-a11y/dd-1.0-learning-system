# 语文与英语知识点缺口续批

2026-11-12按题库质量主线处理二上语文、七上语文和七上英语。新增14道原创题，覆盖13个教材范围；原有数学v6口径和数学题不变，全学科知识点映射升级到subject-v5。

正式题库由1131增至1145题（二年级418、七年级727），章节题版由1057增至1071，schema保持14。12道备用候选题仍未安装。题干、标准答案、解析、易错反馈与主题位置已进入本地逐题审阅包 [questions.html](../../learning_data/verification/subject-gaps-20261112/review-after/questions.html)。页码只表示原创题的教材主题位置，不代表题目摘自教材。

subject-v5共276点、658项要求；当前编辑映射状态为93 configured、294 partial、271 gap。308项明确保留人工核对属性，350项为bounded要求。状态只描述当前映射编辑目标，不代表课程标准完整率、题目质量签署或学生掌握情况。数学旧口径`family_math_coverage_plan_v6.json`未修改。

在隔离一致性副本首次导入新增14题，第二次重复导入新增0；比对确认导入前所有数据库行均保留，只有`questions`新增14行、`question_versions`新增14行、`audit_events`新增1行。正式备份通过完整性与外键检查。该备份和演练材料仍位于本机，不构成独立故障域备份。

验证记录：50项内容/知识覆盖/章节练习测试和29项发布封包兼容测试通过，含旧v10封包兼容。章节练习浏览器复跑在1280视口因旧字段定位断言失败，390视口随后中断；此前部署批记录的390/1280浏览器验收仍保留，但本轮复跑失败也单独记录于[test-results.json](../../learning_data/verification/subject-gaps-20261112/test-results.json)。这次失败尚未作为本批内容缺陷定性，后续应先复核该共享章节练习场景。无模型、OCR或embedding调用。

线上仅更新API和worker到`sha256:34f037086c106495f0446e5153279fd1a3227c493bba1d64bdbd4c927850d05c`；89个运行文件/服务哈希匹配，API与WebUI healthy。网关、代理、WebUI镜像及静态文件未更新。已有身份只读题单返回subject-v5，14题中4道候选可见，私有答案字段未泄露。4个C01容器保持exited；真实手机验收仍按用户要求暂缓。

逐项覆盖、部署与保全快照见[review-after](../../learning_data/verification/subject-gaps-20261112/review-after/index.html)、[data-preservation.json](../../learning_data/verification/subject-gaps-20261112/data-preservation.json)、[test-results.json](../../learning_data/verification/subject-gaps-20261112/test-results.json)。未提交或推送。
