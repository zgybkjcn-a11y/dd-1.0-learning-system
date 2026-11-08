# A09 三个静态样本交付与恢复

2026-11-08：本地候选与恢复包就绪，未发布；实际桌面、手机、打印与家长反馈 pending。[本地验收](../verification/A09-static-samples-2026-11-08.md)与[台账](../plans/dd-next-work-tracker.json)分别记录工程、交付和实际验收。此操作单本身不触发发布。

## 固定范围

三个样本为七上第五章的等式加法性质演示、知识路线和三页章节复习稿。源码取自提交 `deef3199f558ba72bbe3f2ff0c704586674a2232` 的九个文件；Mermaid 11.12.1 本地 bundle、MIT 和 67 个打包依赖的许可记录随包提供。当前工作树桥接文件属于 A07，不能用工作树目录整体替换本包。

包目录：`learning_data/verification/a09-static-samples-20261107T223140Z/release-packet/`。

- 新静态目录：`samples-20261108-a09/`，九个文件。
- `nginx.candidate.conf`：仅替换三条静态 alias，新增本地 Mermaid 路由。
- `nginx.before.conf`、`rollback/nginx.conf`：本批准备时读取的原配置，逐字节相同。
- `rollback/chat-20261107/`：本批读到并核对的四个旧文件，包括来源说明。
- `nginx.forward.patch` / `nginx.reverse.patch`：配置正反向差异。
- `static-changes.patch`：三个原有脚本/样式及来源说明的差异；新增 vendor 文件在清单逐项列出。
- `manifest.json`：19 个文件的哈希；其 SHA256 为 `c149f286216d72cf28da7901f6d528627b45d5d9d285d5495478ba32b397043e`。清单本身为第 20 个文件。

配置基线 SHA256：`fcb3e8131090dbc5f89ad2b07186b0d17b897658a1c8cf9e18562bd3b7d0676a`。本包只支持此基线与 `chat-20261107` 资源；后续基线变化须重新审阅，不放宽哈希检查。

## 准备与验证

以下命令只做本地准备或隔离验证。输出父目录须先存在；目标目录和静态命名必须全新。重复执行换新目录，不删除旧证据。

```bash
python3 scripts/prepare_main_study_samples.py prepare \
  --output learning_data/verification/<新批次>/release-packet \
  --snapshot samples-<新批次名> \
  --active-config learning_data/deployments/family-math-20261105/main-study-20261106/nginx.conf \
  --previous-assets learning_data/deployments/family-math-20261105/main-study-20261106/assets/chat-20261107
```

核对当前已准备包和本地基线：

```bash
python3 scripts/prepare_main_study_samples.py verify \
  --packet learning_data/verification/a09-static-samples-20261107T223140Z/release-packet \
  --expected-manifest-sha256 c149f286216d72cf28da7901f6d528627b45d5d9d285d5495478ba32b397043e \
  --active-config learning_data/deployments/family-math-20261105/main-study-20261106/nginx.conf \
  --previous-assets learning_data/deployments/family-math-20261105/main-study-20261106/assets/chat-20261107
```

省略最后两个参数只验证包本身，不能据此确认活动基线。脚本拒绝软链接、覆盖旧包、异常目录名、配置/资源变化、包内容篡改。清单哈希从本审阅记录取得，不能把待查文件即时计算的哈希当成受信审阅值。

```bash
python3 scripts/probe_main_study_samples_nginx.py \
  --packet learning_data/verification/a09-static-samples-20261107T223140Z/release-packet \
  --expected-manifest-sha256 c149f286216d72cf28da7901f6d528627b45d5d9d285d5495478ba32b397043e \
  --output learning_data/verification/<新批次>/nginx-probe
```

探针使用固定 nginx 镜像、`--pull never`、断网命名空间、只读包和临时自签名证书；仅访问容器内 loopback。候选、回退分别检查语法和 HTTPS 静态资源。探针失败不输出 passed，临时容器清理结果受检查。包内不写日志或测试证书。

## 发布操作单（尚未执行）

发布范围只限此静态包。开始维护时先确认有效指令覆盖实际切换，再执行下面步骤并保留时间、输出与文件哈希；发布前需刷新活动容器事实，本轮没有将历史运行状态冒充当前健康证明。

1. 使用现有 `compose-main-study-20261106.json`，定向确认 `learning-proxy`、固定 nginx 镜像及静态目录/配置挂载。配置映射目标为 `/etc/nginx/dd-learning.conf`，静态目录目标为 `/opt/dd-main-study`。只查询这些字段，不输出环境变量或正式数据。
2. 再运行带两个基线参数的 verify；从活动代理读取加载配置对应文件的哈希、匿名 HTTPS 核对原三路由，必须匹配本包原配置及旧资源。若别的维护已改动、基线不符、命名目录已存在或挂载不符，停止并重新准备，不能强制覆盖。
3. 把九文件快照复制到现有挂载父目录内的全新 `assets/samples-20261108-a09/`，按清单逐文件复核。保留 `chat-20261107/` 原目录。把候选配置以临时检查文件放入同一静态挂载父目录，使用当前代理的 `nginx -t -c <容器内检查文件路径>` 验证真实挂载可用；失败时活动配置不变。
4. 在无并发维护的窗口再次核对基线。保存本次配置文件元数据和哈希。Compose config 是文件绑定时须保持原 inode，用写入既有文件的方式更新；不能用 rename 替换后误以为容器已读新内容。核对容器内 `/etc/nginx/dd-learning.conf` 哈希为候选值，执行 `nginx -t -c /etc/nginx/dd-learning.conf`；失败立即按原字节恢复，禁止 reload。
5. 语法通过后仅 reload 该代理。确认 reload 成功、新 worker 接受请求，匿名 HTTPS 四条路由均 200/no-store、MIME 和哈希一致，原服务健康无退化。记录实际候选配置哈希及资源值；检查失败执行本批回退。无须重建卷、换 Compose、重新注册 Tool 或重绑。
6. 在已登录的真实桌面/手机完成下表并记录；不由维护脚本自动登录、发送聊天或调用模型。删除临时检查文件前保存检查证据，新旧静态快照保留用于复核。工作树里的 A07 桥接与 Tool 不属于此次切换。

本地 verify 只能证明指定文件与包一致，不能替代活动挂载、运行版本和发布后检查。若维护窗口或实际发布范围尚未落实，保留候选状态，继续其他就绪工程任务。

## 本批回退

当新资源加载错误、入口阻断、草稿/练习受影响时，先记录失败事实。确认当前配置确为本包 candidate；如果已变成另一批配置，停止盲目覆盖并重新核对。`chat-20261107/` 原文件应仍在，逐个比对 `rollback/chat-20261107/`；缺失时从本包恢复到其原目录，异值时先记录并查明并发维护。

把本包 `rollback/nginx.conf` 原字节恢复到本次实际活动配置文件（注意文件绑定 inode），确认容器可见同一哈希，`nginx -t` 成功才 reload。恢复后匿名读取原三条路由，确认原哈希、200/no-store/MIME和服务健康。Mermaid 专属 location 随原配置恢复而移除；新目录可保留为审计材料，不需要删除。此回退只恢复本批前一组 alias/资源，不恢复旧 Compose、服务镜像或数据库。

已在隔离 nginx 验证候选 4 路由与回退 3 路由，并用配置正反补丁回放恢复原字节。正式发布后的回退尚未演练。

## 设备与家长检查表

可以先看[离线等式课堂](../../learning_data/verification/a09-static-samples-20261107T223140Z/device-preview/equality-classroom-1280.html)、[三页 PDF](../../learning_data/verification/a09-static-samples-20261107T223140Z/device-preview/chapter-review-1280.pdf)、[离线打印稿](../../learning_data/verification/a09-static-samples-20261107T223140Z/device-preview/chapter-review-1280.html)。这些是历史验证实物的原字节副本。路线截图仅作参考，点击验收需实际候选入口。

| 检查 | 桌面 | 实际家庭手机 | 打印/保存 PDF |
| --- | --- | --- | --- |
| 系统、设备、浏览器版本、操作者和实际时间 | pending | pending | pending |
| 学科伴学→七上第五章→分步课堂→等式的基本性质→观察理解 | pending | pending | 不适用 |
| 先预测，再操作；−6～6、两边同加/仅左边改变，0/负数可理解 | pending | pending | 不适用 |
| 路线节点点按/键盘进入卡片，原页与练习链接可用 | pending | pending | 检查出处链接 |
| 章节复习三页中文/公式/页码 116、120、128，无裁切 | pending | pending | pending |
| 浏览器打印 / 保存 PDF / 离线打印稿所用方式及真实结果 | pending | pending | pending |
| 原聊天草稿、进行中练习保留；换档案/范围不会留下旧内容 | pending | pending | 导出不含身份/手输内容 |
| 离线样本不请求外部资源，断网操作/恢复可理解 | pending | pending | pending |
| 家长可理解性、孩子操作困难、问题与跟进 | pending | pending | pending |

记录每项 passed / failed / pending / 不适用并说明原因，保留错误时的最小必要信息，不复制聊天和学生正文。历史 Chromium 1280/390 自动化、实际三页 PDF 和网络检查可复用；自动截图与模拟视口不能替代真实触屏、系统打印对话框或家长反馈。
