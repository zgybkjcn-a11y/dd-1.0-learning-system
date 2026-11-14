# 教材图片悬浮翻页与放大翻页

已上线：普通教材显示区的上一页/下一页覆盖在图片左右两侧，不再预留两列按钮空间；放大窗口加入同样的悬浮按钮。按钮保留清晰文字、边框、键盘焦点与触摸尺寸，图片内部滚动时停留在可见区。放大窗口缩小到50%时，按钮位置随图片宽高调整，保持在图片上层。

放大窗口连续翻页保持窗口打开及当前缩放比例，底层页码和目录同步更新，跨章时保留练习范围及会话。首页/末页禁用对应按钮；图片加载失败和页请求失败均可在放大窗口内重试。翻页加载中关闭窗口，迟到的返回只更新阅读页，不会重新弹窗。换档/过期/撤回仍清理旧图片与片段。正常顺序阅读隐藏顶部重复翻页按钮，搜索时顶部保留上个/下个匹配。

Chromium145.0.7632.6在390/1280视口完成4项浏览器场景验证，零失败、零跳过。检查通过实际图像矩形与elementFromPoint确认按钮覆盖在图像之上，可直接点击；覆盖内部滚动保持位置、放大连续翻页和125%比例保持、50%按钮位置、29→30跨章/目录同步、首尾禁用、两类失败重试、加载中关闭不重开、图片缩放和键盘打开、练习恢复/搜索匹配/片段撤回/档案切换、无横向溢出。浏览器使用合成教材与临时账户，无外部模型调用或生产作答。本批不重复无变化的教材API测试。

现有取消练习用例等待一条瞬时提示会受服务端恢复刷新影响，本批改为等待取消后的首页状态；原有“已取消”与恢复后的“已跳过”均属于同一取消流程。调试记录browser-check1.log、browser-check2.log保留，最终以browser-accepted.log为准。

[教材桌面](../../learning_data/verification/reader-overlay-20261111/browser/reader-navigation-1280.png) · [教材窄屏](../../learning_data/verification/reader-overlay-20261111/browser/reader-navigation-390.png) · [放大桌面](../../learning_data/verification/reader-overlay-20261111/browser/zoom-overlay-1280.png) · [放大窄屏](../../learning_data/verification/reader-overlay-20261111/browser/zoom-overlay-390.png)。验证文件指纹见validated-files.json。

封包`learning_data/releases/reader-overlay-20261111-final`，128源码文件中仅learning_service/app.py相对上版变化；source set `b8647a939ba9e723c78704c41aff50ecac1cbdfc6ca0d9d47e2ceab0282798d4`，archive `c5f8eb9426828d2c0a11964fca190879011d59e290713999753a041d47ed4feb`。镜像`sha256:e9b9237c22212f03f0eceaac97960f037b93cbd8c5bddbdbf8ce9b69e0b88bd9`；Compose `learning_data/deployments/family-reader-overlay-20261111/compose.json`。仅API/worker更新，各84个运行文件与封包一致，5服务运行、API healthy；其余3服务镜像及启动时间保持。线上UI200并读回悬浮样式与放大翻页控件。

只读核对1121题/schema14，未导入或更改数据库结构，既有模型验收保留。真实家庭手机继续按原安排暂缓，390为模拟视口。未提交或推送。
