# 基线与隔离核验

日期：2026-11-02

- 项目根没有可用 Git 工作树；未执行破坏性 Git 操作。
- 现有 `data/`、`data/webui.db` 和 `batch_ingest.py` 未修改；未读取或输出其中敏感内容。
- 学习服务使用独立 `learning_data/`（部署为 `/var/lib/dd-learning`），源码不导入 `open_webui.*`。
- `python3 -m compileall -q learning_service tests` 通过。
- 依赖版本记录在 `requirements-learning.txt`；部署入口为 `Dockerfile.learning` 和 `docker-compose.learning.yml`。
- `.dockerignore` 排除正式 `data/`、学习数据库/附件和本地测试资料，镜像构建上下文不包含这些目录。

这是代码和目录边界核验，不是正式发布批准。
