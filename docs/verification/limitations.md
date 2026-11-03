# 当前验证限制

日期：2026-11-03

- 早期环境曾观察到 FastAPI `TestClient`/ASGI 栈挂起；2026-11-03 复核时最小 `/health` 探针已在临时目录返回 200。它只证明当前依赖下的本地 HTTP 适配可用，仍不能替代真实 Open WebUI 浏览器、Tools 注册或原生回调验收；完整隔离证据继续采用独立 Compose 容器和宿主 `curl`/Chrome。
- revision 5 独立 Compose 是历史阶段证据；当前 revision 6 的生产边界见 `docs/verification/compose-isolation-2026-11-03-revision6.md`，隔离 Open WebUI 0.12.5 Tool 注册/原生 loader 见 `docs/verification/open-webui-tools-registration-2026-11-03.md`。页面修订/复核申请及删除后恢复重放由确定性回归覆盖。本地 Chrome 曾在 1280px 和 390px 视口完成 `/ui` 上传→复核→确认→错题本合成闭环且无横向溢出，证据见 `docs/verification/page-revision-review-request-2026-11-03.md`、`docs/verification/browser-ui-2026-11-03.json` 和 `.png`。这些结果仍不等同于真实 Open WebUI 浏览器最终可信回调验收。
- 现有测试使用隔离临时目录、直接路由函数和 SQLite/worker 事务，证明确定性业务约束；不替代真实 HTTP、浏览器或 Open WebUI 回调验收。
- 没有获得真实 OCR/模型凭据、预算、脱敏整卷样本或真实学习者授权，因此没有报告识别率、判错率、费用、真实资料外发或 T23 学习效果；本地浏览器证据使用合成 PNG 和确定性 provider。
- 多页 PDF 的页级派生资产、尺寸元数据、失败页状态、私有内容回查和备份关联已由确定性测试覆盖；这不等同于真实 OCR、跨页分题、学科质量或卷面识别准确率验证。
