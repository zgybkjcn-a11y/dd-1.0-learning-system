# 多学科教材、顺序浏览与折叠验证

2026-11-06 已上线。当前两个档案的教材入口按“学科 → 课本 → 单元/章节”选择；无关键词时从章节起始页顺序浏览，每组最多四页，可上一组/下一组翻阅。有关键词时复用已有本地向量检索，过滤年级、文件版本和章节，同页去重后按书内页码升序展示。

## 当前覆盖与边界

| 年级 | 已接入的新版阅读教材 |
| --- | --- |
| 二年级 | 语文上下册、数学上册、道德与法治上册 |
| 七年级 | 语文上下册、数学上下册，英语、道德与法治、历史、地理、生物上册 |

共13册、1,948个向量片段、98个单元/章节/附录区间。用户明确确认二年级学校暂未开英语，已记入持续约定并在界面说明。当前两档案不添加未开设课程；物理八年级、化学九年级开始。其他年级尚未建立档案或接入教材，不能声称全部年级已经完成。

二年级数学下册仍待已授权的离线OCR及逐页转写、内容双重审核；二年级道法和七年级英语/道法/历史/地理/生物下册尚待补齐。界面如实提示缺口，不以旧版补位。新增学科目前提供教材阅读，练习仍是原14道数学起步题，本次未发布新题；原页可见和向量命中不等于题目、答案或内容审核通过。

## 阅读体验

- 结果默认折叠，每页标题显示书内页码与内容主题；可查看定义、课文或对应小节等内容说明。标题依据固定教材目录、小节范围及已核对页内容生成，不冒充逐页独立语义审核。
- 顶部提供全部展开/全部收起；每页均可独立展开或收起，页底的收起按钮返回本页标题，减少长距离滚动。
- 图片在首次展开时加载，放大链接打开同一教材原页。原生折叠控件支持键盘；切换学科、册次、章节或关键词会清除旧结果，并丢弃迟到请求。
- 七上数学115页和144页按升序显示，标题分别为“一元一次方程的定义与等式的性质”“杠杆平衡探究：列一元一次方程”。无关键词浏览第五章从110、111、112、113页开始，不以向量相关度代替章节顺序。

## 二年级道法来源核对

新增二年级道法上册：74页原生文字PDF，新增73个片段，无OCR调用。来源为 <https://keben.app/book/0003>，对照人教社目录 <https://book.pep.com.cn/1284001201251/>、独立新版目录 <http://www.dzkbw.com/books/rjb/zhengzhi/2s_2025/> 及实物编修信息、2022课标后记与目录。四单元为过好节假日、我爱我们班、我的家乡美、我爱我们的祖国。下载站标注的“2024版”不作为版权修订年份；官方页图请求返回403，未声称已完成官方页图比对。

PDF SHA256：`aa412c71473b401f34fee653f2f77d18ef614eea2455c85e32fd3b68f15dbd1c`；文件ID：`8ea51941-29a3-5701-ab5e-07f9b24a7b8a`。文件集合和当前二年级知识库均核对为73个片段，既有25条教材文件记录逐行不变。新增内容均为 `reference_only`，`question_answer_approved=false`。详见[导入核验](../../learning_data/verification/textbook-subjects-20261106/ethics-import-verified.json)及[当前索引](../../learning_data/verification/family-textbooks-20261105/current-textbook-index.json)。

## 验证结果

相关测试46项通过，用时81.39秒：

```bash
DD_FAMILY_GAME_EVIDENCE_DIR=learning_data/verification/textbook-subjects-20261106/browser-final \
python3 -m pytest -q tests/test_textbooks.py tests/test_family_adventure_browser.py \
  tests/test_login_gateway.py tests/test_learning_release.py
```

覆盖98个章节完整顺序分页、无缺页或重复、关键词检索、115/144页排序及标题、390/1280像素布局、整体和单页折叠、键盘操作、图片重试和放大链接，以及身份、CSRF、过期上下文、年级/文件隔离和原数学练习流程。

真实PDF浏览器检查使用合成身份，七上115/144页在手机与桌面均正确解码和放大；各新增学科原图可显示，无脚本错误或横向溢出，外部网络请求为0。13个向量集合均使用本地缓存embedding和章节文本样本得到对应页；无关键词章节浏览不依赖向量匹配。此证据不代替家长真实点击验收，未读取真实家长Cookie。

- [真实页浏览器结果](../../learning_data/verification/textbook-subjects-20261106/real-page-browser-report.json)
- [章节顺序检查](../../learning_data/verification/textbook-subjects-20261106/chapter-browse-checks.json)
- [本地向量检查](../../learning_data/verification/textbook-subjects-20261106/vector-retrieval-checks.json)
- [上线核验](../../learning_data/verification/textbook-subjects-20261106/deployed-verification.json)

上线核验确认：API健康200；13册PDF哈希全部有效；教材挂载只读；实际UI包含学科、折叠、标题和翻页；三处部署源码哈希与工作区一致；HTTPS证书验证及登录303跳转正常。更新前后SQLite integrity为ok，家长1、档案2、绑定1、浏览器会话记录2、题目/版本14、学习会话51、作答/判分50、错题0、provider调用0均保持。原WebUI和代理容器ID、启动时间未变。

## 当前部署与续跑

- 入口：<https://172.19.116.53/learning/auth/login>，保存输入后Ctrl+F5刷新即可，无需重绑。
- Compose：`learning_data/deployments/family-math-20261105/compose-subjects-folding-20261106.json`。
- 镜像：`sha256:32808e7a852fbf23c0e4ef16893cd9d561083ed82f5465b2c823d4b85b1b9434`。
- 最终候选：`learning_data/release-preparation/dd-v1-family-subjects-folding-20261106-final`；52个白名单文件，锁定依赖、禁网构建。
- Source set：`b7833f5993d83d411b64df246787e88be4c7ea1ce3967748cceda26bb6665fa4`。
- 备份：`learning_data/family-backups/family-subjects-folding-preupdate-20261106`，更新前已验证。
- 13册只读PDF：`learning_data/deployments/family-subject-textbooks-20261106/` → `/opt/dd-textbooks`。
- [部署记录](../../learning_data/deployments/family-math-20261105/deployment-subjects-folding-20261106.json)。构建记录中的 `deployed_to_production=false` 是构建阶段快照；实际上线以此部署记录及上线核验为准。

只更新家庭API/worker/gateway，保留网络、TLS、数据卷、原WebUI及代理。早期非final候选和所有旧Compose/镜像保留为历史，勿用其up覆盖新功能。全部未提交改动保留；不提交、不推送、不写Goal，不提升完整V1 T/QA状态。继续遵守[教材约定](../goal/TEXTBOOK-POLICY.md)和既有资料、模型/OCR权限边界。
