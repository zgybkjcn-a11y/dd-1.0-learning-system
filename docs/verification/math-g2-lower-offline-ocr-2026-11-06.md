# 二下数学 106 页本机离线 OCR（2026-11-06）

使用用户已授权的公开教材原图，运行现有 `scripts/review_textbook_ocr.py`，仅写入新的隔离证据目录。未下载模型或依赖，未调用外部/付费 OCR、生成模型或学生资料处理接口；未写入教材索引、生产向量库、题库或判分数据。

## 实际结果

- 原图：`learning_data/textbooks/github-verified-20261106/math-g2-lower-images/001.jpg` 至 `106.jpg`，逐张校验 source-manifest 哈希通过。
- 来源 PDF：`learning_data/textbooks/github-candidates-20261106/lyu-math-g2-lower.pdf`，完整来源与版本仍沿用此前多源核验，不因本次 OCR 改变。
- 引擎：本机 RapidOCR 1.4.4、PP-OCRv4 ONNX，已有 `/tmp/dd-textbook-ocr-libs` 中的三份固定模型；脚本禁用 ONNX telemetry。
- 106 / 106 页识别完成，3,161 条识别行，无空白 OCR 页；其中 623 行置信度低于 0.97。这不是错误率测量；高置信度行也可能漏图形或数学符号。
- 所有页及识别行继续隔离；`fully_verified_pages=0`、`question_or_answer_eligible_pages=0`，新入库/新题发布为 0。
- 每页 JSON 保留原图路径/哈希、识别框、文字、置信度与质量状态；PDF、来源 manifest、106 份 OCR、模型和识别脚本的哈希记录在 provenance 中。原图及历史识别结果保留。

结果目录：`learning_data/verification/math-g2-lower-offline-ocr-20261106/`。

## 转写与数学内容的分别核对

直接查看完整原图，对以下三个页面的部分内容另记转写问题和独立数学复算。复核主体为 Codex 助手；仅覆盖列出的片段，没有批准完整页面或全书，也没有用户/教师签署。纠正、图形描述及独立推导均另存，不改原 OCR、不把计算答案填入教材原文的空格。

| PDF 页 / 书内页 | 转写发现 | 独立内容检查 |
| --- | --- | --- |
| 016 / 10 | 正方形图形丢失，余数分隔符和填空框损坏；缺图的一行置信度约 99.69% | 8/9/10/11 根小棒按每 4 根摆一正方形；17/19 个星星每 4 个分组。分别计算商余数并检查重构式、余数范围和单位 |
| 019 / 13 | “每4根摆一个”后漏正方形，置信度约 99.63%；竖式变成 `4/13`，商 3 被串成 31，填空框缺失 | 11 本平均分给 4 人与每人 4 本的商分别为本/人；20 支铅笔分组题保留多解；除以 8 的最大余数为 7；13=4×3+1 |
| 020 / 14 | `除数413被除数` 丢空间关系；`4/15`、`4/16` 不是分数；酸奶的小棒图形丢失；页底图形和运算空框未正确识别 | 15/16 根小棒、11/12 盒酸奶分别检查商余数；左图 3×3+1=10，右图 4×6+2=26，核查图形计数、关系和单位 |

样本页号来自本次完整 PDF 的实际页标：PDF 016/019/020 对应书内 10/13/14。不能复用其他来源的 PDF 偏移或把文件序号直接当书内页码；后续逐页核对时继续验证。

有余数除法的“商……余数”须按整数除法解读，例如 13÷4 的商是 3、余数是 1；不能转成普通有理数等式 13/4=3。转写应保留题号、图形、空格及竖式结构，计算答案另存为审核依据。

独立复算共 18 个分组/商余数场景，另检查最大余数与印刷重构式；使用整数 `divmod`、乘法重构及 `0≤r<d`，不是重复 OCR 或模型互相赞同。视觉片段记录：[review-notes.json](../../learning_data/verification/math-g2-lower-offline-ocr-20261106/review-notes.json)。

## 可重验的证据与剩余工作

- [report.json](../../learning_data/verification/math-g2-lower-offline-ocr-20261106/report.json)：全部 106 页的隔离状态。
- [provenance.json](../../learning_data/verification/math-g2-lower-offline-ocr-20261106/provenance.json)：来源、脚本、模型和逐页 OCR 哈希。
- [ocr.log](../../learning_data/verification/math-g2-lower-offline-ocr-20261106/ocr.log)：本次逐页离线识别日志。
- [verify-evidence.py](../../learning_data/verification/math-g2-lower-offline-ocr-20261106/verify-evidence.py)：只读重验图像/OCR/复核记录的绑定和已记录计算，不自动重复视觉审核，不批准页面或入库。

```bash
python3 learning_data/verification/math-g2-lower-offline-ocr-20261106/verify-evidence.py
```

仍需对 106 页分别建立完整转写和独立内容复核，包括置信度较高的行、图形、单位、上下文及开放题。上述三页也仍缺完整逐页复核，不能以这些片段代替整页通过。后续导入继续使用最新 `scripts/import_family_textbooks.py` 的完整复核门槛；不要使用容器内旧导入脚本。

当前家庭部署与既有绑定/档案保持；体验与只读服务核对见[家庭体验续跑记录](family-experience-followup-2026-11-06.md)。没有部署修复、Goal 写入、提交或推送。
