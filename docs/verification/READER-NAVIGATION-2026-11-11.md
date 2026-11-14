# 教材翻页与目录同步

已上线：教材图片左侧“上一页”、右侧“下一页”，翻动图片内部滚动条时按钮保持可用；首页/末页相应按钮禁用。顺序阅读与跳页覆盖整本教材，从所选章节进入时仍从本章第一页开始，可连续跨章节阅读。

目录按实际显示页码高亮，自动滚动目录容器使当前章节可见；桌面目录随阅读区停留，窄屏保留可折叠目录。跨章阅读不会修改练习范围、正在作答的会话或进度。搜索仍限制在所选范围，顶部按钮切换上个/下个匹配，图片侧边按钮读取相邻实体页。保留图片放大、原生标题折叠、片段有效性复核及过期/换档清理。

Chromium 145.0.7632.6，390/1280视口，4项浏览器场景与19项教材API/边界/权限测试通过（23项不同用例）。验证左右位置、首尾禁用、29→30跨章与目录高亮、整册跳页、内部滚动与翻页后主窗口位置、目录内部自动滚动、未完成练习保留、搜索匹配与实体翻页区分、加载失败重试、缩放、撤回片段与档案切换、无横向溢出。浏览器使用合成教材及临时账户，未调用外部模型或制造生产作答记录。

原浏览器用例末尾两条“切回档案后范围/会话为空”断言与既有服务端恢复行为不符：旧页面对照也失败，证据baseline-check.log。更新为核对恢复原章节和已取消的复习会话，并等待取消完成后换档；本次没有更改进度恢复实现。调试失败记录保留，最终以browser-accepted.log和passage-and-api-final.log为准。

[桌面效果](../../learning_data/verification/reader-navigation-20261111/browser/reader-navigation-1280.png) · [窄屏效果](../../learning_data/verification/reader-navigation-20261111/browser/reader-navigation-390.png)。验证文件指纹见validated-files.json。

封包 `learning_data/releases/reader-navigation-20261111-final`，128源码文件中仅learning_service/app.py相对上版变化；source set `06053dce0b2fb1042e26c5cfbaf69d4853fcb768ac04808050f0daf6dc46194f`，archive `24a576be1cf3a499155de14f371ea81e1d58117b9aca67f35db64b7b9a3a9c56`。镜像 `sha256:8f59022e3ea8907a11f7a583269046c7812480b05ac811979818b510b58617f5`；Compose `learning_data/deployments/family-reader-navigation-20261111/compose.json`。仅API/worker更新，各84个运行文件与封包一致，5服务运行、API healthy；其余3服务镜像及启动时间保持。

线上UI200并读回新控件与同步逻辑；只读核对1121题、schema14。未导入题库或更改数据库结构，保留既有模型验收。真实家庭手机验收继续按原安排暂缓，390为模拟视口。未提交或推送。
