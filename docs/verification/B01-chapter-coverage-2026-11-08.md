# B01 七上第二章内容覆盖表验收

日期：2026-11-08（Asia/Shanghai）；执行/内容关系核对角色：assistant。交付为独立离线候选，不代表发布、教师签署、整页审核、真实模型或家庭体验验收。

## 固定输入与本批范围

开始时 `main` 工作区干净，HEAD `cd4ad61b44597696d6c59495b489595e68123706`；未查询远端或运行容器。先读交接、续接、两份计划、25项台账及A09验收。独立证据目录：`learning_data/verification/b01-chapter-coverage-20261108T020031Z/`。

公开输入是固定旧概念库、60题应用题库、教材目录源码和14题起步题准备源码；起步题没有本章精确映射，未归入本章题量。原有18概念/20精确题映射的知识参考接口保持原样。第二章12道应用题的4条旧映射沿用，8条新增关系仅存在B01覆盖候选，逐条按题干、提示和解析核对并注明助手身份。

教材固定为依据2022年课标修订的人教版七上现行新版，书内24–67页，PDF偏移+7；原件SHA256 `d995a2072c2b00418eacf1fdfc7a00234953592f5fba61a4b227731c8a19fdd8`。读取原生PDF文本核对目录及相关页码，没有OCR、模型调用、学生资料或正式数据库访问。原生页文本留本批 `source-locations/`，只证明局部定位，不提升为完整页审核。

五片段清单SHA256 `d1bf256db814afcf35ff22f28ad32fd4577b4608e12f9d069b7f72cfc8cacd63`，用现有校验器核对PDF、图片、复核/语义证据绑定及当前北京时间2026-11-08。5个片段revision1有效至2026-12-07（含当天）；没有重跑历史A01–A09验收或语义核算脚本。

## 实际覆盖与数量对账

本批盘点19行：13本章知识点、3先修回顾、1本地检查、2综合实践；不声称已穷尽全书/全章所有知识。下表页码均为书内页，先修定位明确保持第一章；片段与教材定位分开。

| 知识点 ID | 教材定位 | 有效片段 | 本地讲解 | 简单/正常/困难题 | 复习资源定位 |
| --- | --- | --- | --- | --- | --- |
| `g7-sign` | 2/9 | 留空 | 有 | 4/4/2 | 60 |
| `g7-absolute` | 13 | 留空 | 有 | 0/0/2 | 60/61 |
| `g7-opposite` | 11 | 留空 | 有 | 0/0/0 | 61 |
| `g7-add` | 25/27 | 27 | 有 | 3/3/3 | 60 |
| `g7-subtract` | 30/31 | 31 | 有 | 2/3/2 | 60 |
| `g7-target` | 留空 | 留空 | 有 | 4/4/4 | 62 |
| `g7-ch2-add-laws` | 28/29 | 留空 | 留空 | 0/0/1 | 60 |
| `g7-ch2-multiply` | 39 | 留空 | 留空 | 0/1/0 | 60 |
| `g7-ch2-reciprocal` | 40 | 40 | 留空 | 0/0/0 | 61 |
| `g7-ch2-multiply-laws` | 41 | 留空 | 留空 | 0/0/0 | 60 |
| `g7-ch2-distributive` | 41 | 41 | 留空 | 0/0/0 | 60 |
| `g7-ch2-product-sign` | 42 | 42 | 留空 | 0/0/0 | 61 |
| `g7-ch2-divide` | 43/44 | 留空 | 留空 | 0/0/0 | 60 |
| `g7-ch2-power` | 51/52 | 留空 | 留空 | 0/0/0 | 60 |
| `g7-ch2-mixed` | 53 | 留空 | 留空 | 0/0/0 | 60 |
| `g7-ch2-scientific` | 54/55 | 留空 | 留空 | 0/0/0 | 61 |
| `g7-ch2-approximate` | 55/56 | 留空 | 留空 | 0/0/0 | 61 |
| `g7-ch2-base-conversion` | 63/64 | 留空 | 留空 | 0/0/0 | 留空 |
| `g7-ch2-base-addition` | 64 | 留空 | 留空 | 0/0/0 | 留空 |

独立题量12/12，旧映射4、新助手候选8，每档4题；共42次题目与知识点关联（含重叠），不能把逐行数量相加当题量。5/5有效片段分别映射加法、减法、倒数、分配律和积的符号，未映射有效片段0。6/19行有现有本地讲解，7/19行有练习关联，17/19行有明确教材复习资源；其余字段按真实缺项留空。

多个概念虽然与片段在同页，却没有片段映射：乘法交换/结合律不借用分配律引文，两数乘法不借用多因子符号引文。除法、乘方、科学记数法、近似数只有局部教材定位，没有有效片段、本地讲解或应用题映射。“核对题意和单位”无教材页码；相反数无独立练习映射。综合实践两行的复习资源留空。

实际复习卡数、到期列表、延迟观察全部为null；未读取运行档案，不把教材回顾题定位当成完成了实际复习。

## 定向验证

最终单元/计数与拒绝契约：`unit-final-r2.xml`，22 passed / 0 failed / 0 skipped。测试使用公开元数据和合成片段；涵盖独立分母/重叠计数、未映射保留、无来源留空、先修不变章、题版/来源指针漂移、越界、重复、篡改、过期/失效为空、HTML转义、不泄漏正文、禁止覆写旧证据和纯导入不建库。`unit-r1.xml`的21项为新增来源指针拒绝用例前的历史运行，单独保留，不与最终计数相加。

`browser-final-r2.xml`：2 passed / 0 failed / 0 skipped，Chromium145.0.7632.6，390/1280两宽度。合成覆盖数据、离线context、所有请求拦截；检查19行、缺项、展开题目ID、无文档水平溢出、无外部请求或页面错误；截图在`browser-final-r2/`。沙箱内r1长期无结果后中止（exit130），r2诊断在首例失败后整体60s超时（exit124，无完整JUnit），均保留attempt记录，不计通过。随后经授权在沙箱外执行同一离线浏览器组，2项通过。截图复核发现手机列宽过窄后增加最小列宽/横向滚动和列宽断言，最终r2在新目录再次2项通过；原先通过的`browser-final.xml`与截图保留，不累加分母。

本机教材定向出表：`packet-final-r2/coverage.json`与HTML成功生成，19行/12题/5片段对账；报告不包含片段正文、上下文或图片。四个公开输入、教材PDF、原生目录/页文本、片段清单与图片/复核证据均固定；出表前再次比较输入及当前日期。默认测试不依赖这些本机私有材料。

```bash
python -m pytest -q tests/test_chapter_coverage.py --junitxml=unit-final-r2.xml
python -m pytest -q -m browser tests/test_chapter_coverage_browser.py --junitxml=browser-final-r2.xml
python -m scripts.prepare_chapter_coverage \
  --bundle learning_data/verification/textbook-passages-20261107 \
  --textbook-dir learning_data/textbooks/pep-current-20261105 \
  --output-dir learning_data/verification/b01-chapter-coverage-20261108T020031Z/packet-final-r2
```

环境复用A03锁定Python3.12.12与Chromium145.0.7632.6；本批不安装依赖，不重复未变化的全套服务/Tool/实物验收。

## 交付与保全

源数据：`learning_service/data/family_chapter_coverage_v1.json`；生成器：`scripts/prepare_chapter_coverage.py`；测试：`tests/test_chapter_coverage.py`、`tests/test_chapter_coverage_browser.py`；[使用/回退说明](../open-webui-reuse/chapter-content-coverage.md)。

本批离线包：`learning_data/verification/b01-chapter-coverage-20261108T020031Z/packet-final-r2/`。`manifest.json` SHA256 `7e18ee3ea339583c111c516bc965713c031c4f7bce7d10b5cc14c8ca27a97944`；其中coverage.json/HTML哈希逐文件记录。源码与增量另由本批 `source-manifest.json`、`increment-manifest.json`、`b01-increment.patch`及`delivery-validation.json`定位。

旧概念库、题库、教材原件与五片段历史目录逐文件哈希保持；没有改动服务、Tool、主站静态资源、范围选择、发布配置或生产数据。线上运行观察仍沿用A01，未刷新。新报告和原生文本核对材料留忽略目录，没有新建独立故障域备份或恢复验收。

本批未提交/推送/部署。回退仅撤回离线候选及文档入口，不影响现有运行版本。A09发布、家庭设备和家长验收继续pending；B01验收的是可核对覆盖表及缺口，下一项B02按缺口准备合格备用题并冻结题版，真实1/3/7天观察另记。
