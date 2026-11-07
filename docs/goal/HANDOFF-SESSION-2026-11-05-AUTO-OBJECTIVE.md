# 家庭数学版：家长已绑定，错题知识目标自动匹配已上线

后续更新（2026-11-05 20:54）：用户选择活泼闯关风格后，数学探险队界面已上线，自动知识目标保留。当前镜像和 Compose 已更新为[新界面交接](HANDOFF-SESSION-2026-11-05-GAME-UI.md)中的版本；本文保留上一版实现和部署历史。

更新：2026-11-05 19:49（Asia/Shanghai）。工作目录、未提交改动及完整 V1 执行限制沿用原交接。当前仍是一个已有 Open WebUI 家长账号、七年级和二年级两个数学档案。

家长已在 Windows 原生 Edge 输入真实账号凭据，助手填写私有启用码后完成一次绑定并确认进入 `/learning/ui`。WSL Chrome 曾无法接收用户键盘输入，换 Windows 原生浏览器后用户确认恢复；物理键盘问题的根因没有进一步定位。后续同一家长登录时启用码可留空。详见[首次使用记录](FAMILY-FIRST-USE-2026-11-05.md)。

用户提出“错题本的知识目标能不能自动填”后，已修改并部署：输入题干时，在当前档案已有知识目标中匹配简单整数算式，自动选中目标，保留手动改选和“暂不分类”。刷新今日任务不覆盖手动选择，保存完成或切换档案会重置自动匹配状态。

| 题干示例 | 当前档案 | 自动选择 |
| --- | --- | --- |
| `23＋15`、`56－19` | 二年级 | 100 以内加减法 |
| `6×7`、`6乘以7` | 二年级 | 表内乘法 |
| `−3−（−5）`、`12减去−3` | 七年级 | 理解减去负数的运算方向 |

支持半角、全角和常见运算符写法。只有一个明确匹配时自动选择；超出当前范围的算式、小数、代数、复杂或混合题型、一般应用题及其他知识目标仍留空，可手动选择。不会根据“当前只有一个目标”就强行分类，不调用模型或 OCR。

部署使用新固定本地镜像 `sha256:925af49f45fb70bf6b07312a633c62998696546dcb18a4bdceab54e68371b12d`，schema 仍为 11。50 文件源码候选中只有 `learning_service/app.py` 相对旧家庭版发生变化，未改契约、迁移或 provider 配置。独立新 Compose 仅修改 API、worker、gateway 的镜像字段，原 proxy、网络、证书、数据卷及原 WebUI 容器保持。旧 Compose、候选、镜像和部署记录均保留。

当前配置与检查：

```bash
docker compose --env-file /dev/null -p dd-family-math -f learning_data/deployments/family-math-20261105/compose-auto-objective-20261105.json ps
```

不要用旧 `compose.json up` 覆盖新镜像。停止或恢复仍用同一新文件的 `stop --timeout 60` 或 `start`，不要删除 `dd-family-math_data`。

验证为两组：家庭功能和新浏览器验证 **6 passed**，已有手动保存回归 **2 passed**。新浏览器使用合成 ASGI 数据，覆盖 390px/1280px、题型和范围匹配、手动选择/留空、任务刷新、切换清理、保存后正确目标与复习卡，无页面错误或横向溢出。最初沙箱内 HTTP/浏览器测试没有继续输出，旧进程以 143 终止；沙箱外六项验证通过。没有重跑旧 P0、四格式或全量。

实际新 API 已提供自动匹配页面代码，HTTPS health 为 200，四服务运行且 API 健康。更新前后聚合计数一致：家长记录 1、档案 2、题目 14、绑定 1、浏览器会话记录 1；练习、作答、错题、provider 调用仍为 0。两个档案的真实作答、刷新恢复和错题试用仍待家长操作，不能把新合成验证写成真实学习观察。完整 V1 的 T/QA/Goal 状态未提升，未执行 Goal 写入。

更新前在容器 `/tmp` 创建的快照导出失败，不能作为已留存备份；失败后仍执行了更新，这是执行顺序上的失误。更新后已在持久数据卷的 `backups/` 子目录创建快照并成功复制到本地，manifest 校验和及 SQLite integrity 均通过，数据库快照 SHA256 与更新前生成的快照回执一致。使用[新备份位置](../../learning_data/family-backups/family-auto-objective-postupdate-20261105/)；没有恢复或重建生产库。

证据：[部署记录](../../learning_data/deployments/family-math-20261105/deployment-auto-objective-20261105.json)、[新源码候选](../../learning_data/release-preparation/dd-v1-family-auto-objective-20261105/manifest.json)、[本地构建](../../learning_data/verification/family-auto-objective-20261105/build/build.json)、[部署后只读状态](../../learning_data/verification/family-auto-objective-20261105/runtime-postdeploy.json)。源码候选和构建记录中的“未部署”是各自产生时的阶段边界，后续实际上线以新部署记录为准。

下一步：家长保存当前表单内容后刷新页面，试用自动目标选择，并完成两个档案各一道题、判分/刷新/切换和手动错题的实际反馈。继续保持数学优先、mock/外发关闭/学习预算 0；不读取既有 WebUI 数据/环境秘密，不改根 Compose、batch_ingest.py 或 Tools，不 reset/checkout/clean/commit/push，不创建/更新/完成 Goal。
