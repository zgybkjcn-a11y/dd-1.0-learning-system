# 源码管理与敏感文件排除基线

日期：2026-11-03（Asia/Shanghai）

核对结果：项目根目录及其父级均没有 `.git` 元数据；项目根目录此前也没有 `.gitignore`，不存在更上层的仓库边界。为了满足 T01 的源码版本管理要求，本轮在项目根建立了本地 Git 仓库，并以当前已存在的 DD-1.0 源码、测试、部署定义、设计和验收文档创建首个基线提交。初始化和提交均未覆盖或改写工作区文件；该提交是当前可用快照，不伪称能还原缺失的历史 diff。

根目录 `.gitignore` 覆盖运行数据、附件/备份/导出、环境凭证、数据库/WAL、Python 缓存和本地开发工具状态。`git check-ignore -v` 实际确认 `data/`、`learning_data/`、`.env`、`.pytest_cache/`、`/docker-compose.yml` 与 `/batch_ingest.py` 命中精确规则；`.dockerignore` 仍独立控制镜像构建上下文。两个原有顶层文件留在本机并按精确路径忽略，不纳入公开仓库；数据库和运行资料也已忽略。

这建立了后续可审阅的源码版本历史，并保留了安全忽略规则。初始快照前没有仓库元数据，因此无法可靠区分哪些既有文件曾由用户单独修改；后续 diff 从该基线开始。脱敏发布状态和运行边界见 `docs/verification/release-manifest-2026-11-03.json` 与 `docs/verification/baseline.md`。

2026-11-03 发布核验：公开仓库为 <https://github.com/zgybkjcn-a11y/dd-1.0-learning-system>，默认分支为 `main`，远端 `master` 已删除。初始交付提交 `ed67875d4eb189a226f30a38f71456be5b3233c7` 已包含在 `main` 历史中；GitHub API 确认仓库可见性为 `PUBLIC`，`git ls-remote` 与本地分支核对一致。提交作者使用 GitHub noreply 地址。发布前 `pytest -q` 为 78 passed，Goal 一致性、compileall、Compose 配置与 `git diff --check` 均通过。
