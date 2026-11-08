# 五片段运行接入（A07 本地候选）

能力默认关闭。启用后，非空教材查询只查服务器固定的助手核对片段，不请求向量检索或任何模型；当前仅覆盖七上数学第二章的五条规则/定义。空查询仍按页阅读。无依据、低相关、组合依据不足分别返回，坏材料返回错误，均不从未审核索引补正文。

## 配置与材料

维护者在独立发布候选中设置以下变量；本批未改现用 Compose、未启用正式服务：

```dotenv
LEARNING_TEXTBOOK_PASSAGES_ENABLED=0
LEARNING_TEXTBOOK_PASSAGES_DIR=/readonly/textbook-passages
LEARNING_TEXTBOOK_PASSAGES_SHA256=d1bf256db814afcf35ff22f28ad32fd4577b4608e12f9d069b7f72cfc8cacd63
LEARNING_TEXTBOOK_DIR=/readonly/textbooks
```

只有核对材料、版本和当前有效期后才把开关设为 `1`。固定清单哈希由服务器配置给出，不信任材料目录里的相邻 checksum。目录及祖先不得为软链接。片段目录需只读挂载 `passages.json`、五张 `source/*.png`、`semantic-checks.json`、`verify_semantics.py`；PDF 目录包含对应的 `math-g7-upper.pdf`。校验脚本只验证字节哈希，绝不执行材料中的 Python。原图、教材正文、真实评测集和运行资料继续留忽略目录，单独备份，不进入公开源码包。

当前材料原始位置为 `learning_data/verification/textbook-passages-20261107/`，PDF 为 `learning_data/textbooks/pep-current-20261105/math-g7-upper.pdf`，PDF SHA256 为 `d995a2072c2b00418eacf1fdfc7a00234953592f5fba61a4b227731c8a19fdd8`。五片段有效期截至 **2026-12-07（北京时间）**。`reviewed_on <= 当前日期 <= valid_until`；北京时间次日零点失效。没有历史日期请求参数或环境绕过开关。

启动时保存脱敏状态 `app.state.passage_status`（ready/disabled/unavailable）。查询、详情、绑定原图都重新读取清单、源 PDF、图片与审核证据，并在返回前再核对快照。启动材料错误不会阻止其他原页阅读；后续修复字节仍须符合配置 pin。更换清单须审阅新材料并更新配置，已有证据只有在当前包仍有效时可用，审核 revision 改变产生新证据 ID。

## 接口和引用

`POST /api/v1/textbooks/search` 模型参数仍仅 `query/book_id/chapter_id`，浏览器还可用既有 `page_offset`；不接受路径、日期、身份或 hash。片段查询最多120字。身份、年级与 context revision 来自既有授权流程。

启用后的响应 `mode=passages`。旧 `items` 保持页级位置和空文本；新增 `passage_result` 为 `dd-textbook-passage-result-v1`，包含 `manifest_sha256`、服务器 `checked_on`、`timezone`、scope、完整 items、检索覆盖、grounding 和逐字 `answer.claims`。每项返回 text/context/evidence 及服务器详情/图片路径。覆盖仅指 `loaded_reviewed_excerpts_only`，不代表全章或全书。OpenAPI 包含具体响应模型。

- `GET /api/v1/textbooks/{book_id}/passages/{evidence_id}?chapter_id=2`：重新授权并检查当前材料，返回 `dd-textbook-passage-detail-v1`。
- 同路径加 `/image`：检查相同证据版本，返回绑定审核的原页 PNG，图片 hash 与 evidence 一致。
- 所有响应 `Cache-Control: no-store`；详情只接受单个可选 chapter_id，未知或重复参数拒绝。
- 错误分别为 `TEXTBOOK_PASSAGES_DISABLED`（404）、`TEXTBOOK_PASSAGE_NOT_FOUND`（404，失效/撤回/越界）、`TEXTBOOK_PASSAGES_UNAVAILABLE`（503，坏或缺材料）、`TEXTBOOK_PASSAGE_STALE`（409，请求途中状态变化）。旧会话/档案冲突沿用原错误契约。

Tool 1.2.0 保留六个公开方法。它独立检查全文哈希、证据 ID、页身份、有效日期与能力标记；逐项读详情，再重新查一次完整结果和会话，任何变化停止引用。JSON 的 `answer.claims` 与原生 citation document 均为完整逐字引文；citation source ID、page_evidence_id、双页码和审核 hash 一一绑定。链接带 `studyEvidence` 与当前 revision，打开时再检查。

工作台展示全文、上下文、双页码、有效期和原页，导航旧命中也重新读详情，加载图片后再次核对。到期计时清除片段，切换页面可见状态时清除并提示重新查询；档案切换清理旧内容。已保存聊天中的历史文字无法追溯删除，重开引用必须通过当前检查。无实时撤回推送，持续打开页面的撤回会在下一次展示/导航/可见性变化时核验。

所有片段始终 `teacher_reviewed=false`、`fully_reviewed_page=false`、`eligible_as_grading_basis=false`、`can_answer_from_textbook=false`。助手双步骤核对不等于教师签署或整页通过，不生成解题答案，不赋予判分资格。

## 发布与回退

新 `reuse-runtime-textbook-passages-v1` 白名单含三个运行模块、六方法 Tool、family-bridge 和本文；运行模块不导入 scripts。历史 `reuse-runtime-study-workbench-v1` 和更早 profile 继续验证。Tool 单文件仍需按 A08 独立升级现有 ID，服务源码包包含文件不等于已注册。

兼容组合：历史1.0.0和旧1.1.2 Tool + 新服务只显示页定位并说明 incomplete；新 Tool + 关闭能力/A05页级服务保留原页能力，不升级原文权限；新 Tool + 新服务支持助手核对片段。历史线上服务缺页级evidence，不能单独换新Tool。关闭片段开关恢复既有页定位流程，所有旧片段详情和图片返回 disabled，绝不把旧引用缓存恢复为可引用正文。回退服务/Tool 前使用对应 profile 和文件哈希；不覆盖现用 Compose、不注册重复 Tool、不重建卷。
