# 二年级、七年级缺册补齐验收

2026-11-12 已上线原页阅读教材 **20 册、152 个目录范围**：二年级语文、数学、道德与法治上下册共 6 册；七年级语文、数学、英语、道德与法治、历史、地理、生物上下册共 14 册。二年级英语按此前学校安排暂不开设，物理、化学仍按开课年级安排。

本批新增 7 册、54 个目录范围，全部采用六三学制人教社依据 2022 版课标修订的现行新版。教材齐全指以上已确认开设学科的上下册原件与阅读功能，不表示题库、知识点、教师审核已齐全。

| 新增教材（均为下册） | PDF 原页数 | 可阅读书内页码 | PDF 页码减书内页码 |
| --- | ---: | --- | ---: |
| 二年级数学 | 106 | 1–97 | 6 |
| 二年级道德与法治 | 70 | 1–61 | 5 |
| 七年级英语 | 130 | 1–119 | 9 |
| 七年级道德与法治 | 114 | 1–104 | 7 |
| 七年级历史 | 142 | 2–133 | 5 |
| 七年级地理 | 126 | 1–118 | 5 |
| 七年级生物 | 143 | 1–136 | 5 |

完整文件保留封面、目录及后记；阅读器延续既有书内页码导航。历史书内从第 2 页开始有编号，不编造第 1 页。二下数学包含额外前页，因此偏移为 6，未套用其他小学教材的偏移。

## 版本与来源

[逐册来源、PDF 哈希与逐页渲染记录](../../learning_data/textbooks/missing-lower-20261112/verified-source-manifest.json)绑定准确原件；[运行目录元数据](../../learning_service/data/textbook_lower_reading_v1.json)记录目录、页码和哈希。

- 人教社 [当前官方目录](https://jc.pep.com.cn/)的六三学制学生用书，交叉核对封面、编修信息、后记及独立目录。官方目录留存为 `pep-official-catalog.json`，选册留存为 `official-selected-books.json`。
- 二下数学复用此前核对的 GitHub 完整 PDF（SHA256 `aa34f13d5d305ed6761052d4c24d0cd0c101930e665290bc1bd22b6b884fd060`），继续隔离原有未全书审核 OCR。
- 二下道法采用[国家智慧教育平台新版资源](https://basic.smartedu.cn/tchMaterial/detail?contentType=assets_document&contentId=9d7e48c5-1d0c-4bad-99b6-d30f6f6d5d07&catalogType=tchMaterial)公开原页图片，共 70 页，本地合成阅读 PDF，无 OCR 文本层。逐张来源与哈希保留在 `ethics-g2-lower-official-images/manifest.json`；新版四单元为“我乐观 我向上”“大自然，谢谢您”“传统美德我弘扬”“播下梦想的种子”。
- 五本七下 PDF 来自课本网公开下载，分别使用 0192、0086、0195、0180、0190。下载站“2024”是系列标签，电子版版权页未填写具体印次，不据此编造出版年或 ISBN；目录与官方现行书及独立的 2025 春版目录对应。七下英语为 8 单元，生物新增植物生活与人体生理健康（一），均排除旧版内容。
- 拒绝二下道法 0004（2017 旧版）和误定位的 0178（实际是八上地理）；未用于补位。

这些原件只提供阅读参考。新 7 册不创建虚假的向量集合，关键词查找按钮暂不可用，可用目录、跳页和翻页定位；服务端同样阻断向量检索。未调用模型、OCR、embedding，未新增题目或授予答案/判分资格。

## 验证结果

证据目录：`learning_data/verification/textbook-completion-20261112/`。

- `originals-check.json`：7 本完整文件的 831 页逐页本地渲染成功；逐册核对封面、编修页、目录、首末页、章节起止。该检查不等于逐页内容/答案审核。
- `unit.log`：66 passed，教材 API、页证据、年级隔离、整册连续阅读、无索引回退和发布封包检查。
- `compatibility.log`：99 passed，既有片段接口、OpenAPI、发布配置及兼容回归；与上项有重复模块，不相加声称独立用例数。
- `browser-accepted.log`：390/1280 两视口共 2 passed，7 册逐一验证目录选择、禁用关键词查询、无题状态、跨章翻页、放大翻页、目录高亮、末页禁用，切回旧册恢复查找。首次测试脚本误引用不存在的切换按钮，修正测试后通过；首次失败日志保留。真实手机验收仍按用户要求暂缓。
- `live-check.json`：线上目录为 6/14 册；7 册首末原页均验证，当前既有二年级上下文的目录及 2 本新增教材原页通过真实认证 HTTP 读取，没有切换真实学习者。正式覆盖清单仍为 subject-v5，章节题源 1071。
- `data-preservation.json`：50 张表、3383 条既有行逐行哈希完全一致；1145 题（二年级 418、七年级 727）、schema14 不变。原 13 份 PDF 哈希完全一致，只新增 7 份原件。
- `health-after.json`：家庭 API/worker/gateway 正常，API/WebUI healthy；proxy、WebUI 与 C01 启动时间及状态保持；4 个 C01 容器仍 exited。

## 发布与保全

源码以现行 subject-v5 发布封包为基础，仅叠加 `textbooks.py`、`evidence_contracts.py`、`app.py`、新增教材目录 JSON、发布白名单脚本及 OpenAPI；[变更清单](../../learning_data/verification/textbook-completion-20261112/source-diff.json)确认其余文件与线上封包完全相同。本地 math-v15、subject-v16 和三道未安装数学候选均保留，未随本次发布。

- 发布包：`learning_data/releases/textbook-completion-20261112-final/`，profile `reuse-runtime-textbook-completion-v12`，134 个源码文件。
- 镜像：`sha256:6014a23756647d72fea8afaa074fc05b4fab7cff6e804d570bc34cc23e21c6f6`。离线锁定依赖、无缓存构建；API/worker/gateway 各 90 个运行文件哈希匹配。
- Compose：`learning_data/deployments/family-textbook-completion-20261112/compose.json`；仅更新以上三个家庭服务的镜像字段。gateway 同步是为了新册原页证据与哈希一致，不然旧 gateway 不认识新增 PDF。
- 停止这三个服务后完成校验备份：`learning_data/verification/textbook-completion-20261112/private/backup/`，收据与验证在同级证据目录。随后原数据卷原位启动；无题库导入或迁移。
- 如需回退，使用此前 subject-gaps Compose 的 API/worker/gateway 镜像配置，保留当前数据卷及新增 PDF；禁止用旧备份覆盖新使用记录。新增原件对旧目录无影响。

后续题库质量主线仍参考交接第 5 节：先为已审清的上册 20 项缺口准备本地候选并复核，再处理下册。新增 7 册尚无正式配题，未建立完整知识点清单，必须逐册核验再补题。全书 OCR 审核、课程标准交叉核对、教师签署和真实难度校准继续保留。未提交或推送。
