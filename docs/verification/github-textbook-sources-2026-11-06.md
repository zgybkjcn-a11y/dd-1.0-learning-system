# GitHub 新版教材实物核查

2026-11-06 按用户建议检索 GitHub 仓库、分支和未合并PR，并下载候选PDF检查。结论：**GitHub确实能补齐此前缺少的两本二年级下册完整文件；语文还找到了可直接提取文字的新版，无须继续OCR这本书。** 官方网站下载受阻不能等同于没有其他公开来源。

| 来源 | 实物结果 | 本项目处理 |
| --- | --- | --- |
| [LYUGUISONG/Textbooks](https://github.com/LYUGUISONG/Textbooks) | 数学下册106页、语文下册130页；均图片PDF。全部页图像可解码，页数与人教官方阅读器一致；版权页、编者、目录与官方新版一致 | 两本已下载；数学106张原图已单独备齐，待离线OCR及双重审核 |
| [hantang/yuwen 的 docs 分支](https://github.com/hantang/yuwen/tree/docs/02b-%E4%BA%8C%E5%B9%B4%E7%BA%A7%E4%B8%8B%E5%86%8C) | 新版语文下册130页、可提取文字39,110字符，嵌入正文/拼音字体。目录含《我不是最弱小的》《大禹治水》，与官方现行新版一致 | 优先采用，已增量导入129个参考片段 |
| [TapXWorld/ChinaTextbook 主分支](https://github.com/TapXWorld/ChinaTextbook) | 下载的语文二下131页，版权页2017年版；含《当世界年纪还小的时候》等旧目录 | 排除，不以仓库最近更新时间认定教材新版 |
| [TapXWorld PR #210](https://github.com/TapXWorld/ChinaTextbook/pull/210) | 尚未合并；语文二下128页扫描版，目录为新版，有其他水印 | 留作候选，优先采用字体PDF；该PR中的数学是苏教版，不能代替人教版 |
| [YuppyChen/ChinaTextbook-2026](https://github.com/YuppyChen/ChinaTextbook-2026) | 仓库名带2026，但语文二下131页仍为旧编排：课文第7课《一匹出色的马》，第23课《祖先的摇篮》 | 排除；仓库名年份不能证明版次 |
| [SteveTDX/pep_books](https://github.com/SteveTDX/pep_books) | 下载工具，非现成教材文件库，且默认五四学制 | 未执行仓库代码，未用于本次下载 |

人教数学下册目录依次为“时间在哪里、有余数的除法、数量间的乘除关系、万以内数的认识、万以内的加法和减法、数学连环画、复习与关联”。GitHub数学PDF的目录、主编王长平/分册主编刘丽、后记2022课标依据及ISBN 9787107389139均已直接查看。语文新版编修委员会、目录及ISBN 9787107406027也已对照。官方目录与国家智慧教育平台元数据继续作为版本依据，GitHub只作为文件来源。

图片版还与此前缓存的人教官方图作了对比：数学20页、语文3页的版面高度一致；均保留量化差异记录。此项是来源交叉验证，不是文本或语义审核。原始官方图、旧OCR、旧文件全部保留。数学PDF第104页为正常空白页、第105页后记、第106页封底，未把空白附页当下载失败。全部106张图唯一且可解码；这证明文件结构完整，不等于逐页内容已经审核。

当前参考库从11册/1,746片段增至 **12册/1,875片段**。新增语文 file_id `740e99d2-bc61-5cd8-81f0-7c529371dc63`，关联原新版二年级库 `44c8e0ce-74a8-553d-b7e8-d90941e9f62d`。仅使用已缓存本地embedding，未调用外部模型或OCR。既有24条教材文件记录经比较不变。未发布新题，也未改变家庭版部署/登录/学习记录。

可提取文字不代表所有提取字符正确：语文PDF的拼音嵌入字体提取有非标准字符，已在manifest记录限制，必须查看PDF原页，不能用作拼音答案。所有片段均为 `reference_only`、`question_answer_approved=false`。题目、标准答案和判分仍须单独核验。数学下册仍未入当前检索索引。

文件在 `learning_data/textbooks/github-candidates-20261106/`，版本/页图/校验值/导入核对在 `learning_data/verification/github-textbooks-20261106/`。数学完整图在 `learning_data/textbooks/github-verified-20261106/math-g2-lower-images/`。选用语文PDF及逐页文本同时存于 `learning_data/textbooks/pep-current-20261105/chinese-g2-lower*`。

固定来源：LYUGUISONG仓库commit `c6c736bafe30f238e904a83308ca651109a39b4a`；hantang docs commit `b3fb819c37b7e5c60ce4c62d3e9c45543168530f`。下载校验了Git blob或LFS SHA256。TapXWorld数学候选下载超时，留下partial文件，未当成成功下载，也未据此声称已实测其数学内容。已找到完整新版来源，无需继续重下这个候选。
