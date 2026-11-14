# 教材页标题对齐修正

已上线：教材原页卡片的小三角和当前页标题从第一行开始。将标题display:block改为inline，移除上下margin，保留原生summary折叠行为；窄屏长标题自然换行。

Chromium 145.0.7632.6在900和390宽度完成修改前后对照、首字符位置测量、无横向溢出、鼠标折叠与空格键展开检查。仅一次性视觉核验，未新增永久测试。修改前首字符相对summary顶部41.19px，修改后10px，位于首行且在三角右侧。

[桌面对照](../../learning_data/verification/reader-summary-20261111/after-900.png) · [窄屏效果](../../learning_data/verification/reader-summary-20261111/after-390.png)。证据：layout-check.json、live-check.json、runtime-hashes.json、final-health.json。

封包 learning_data/releases/reader-summary-20261111-final，128源码文件中仅learning_service/app.py变化；source set 4fc07aadc9dca9d23bb2daf4f56002539ee018bc344a4e93c253483f1826159c。镜像sha256:5d06454f7f81be4e020b7796b56262371b92d89a5d4f27f43d59ecd81c1e8d1d，Compose learning_data/deployments/family-reader-summary-20261111/compose.json。API/worker各84个运行文件与封包一致，5服务运行，API healthy，其他3服务镜像与启动时间保持。线上UI200并核对新CSS，题库1121、schema14；未执行题库导入或数据库结构变更，保留既有模型验收。没有提交或推送。
