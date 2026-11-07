# DD-1.0 V1 OpenAPI 契约

`openapi-v1.json` 是由 `learning_service.app.create_app().openapi()` 生成的版本化接口快照，供交接、隔离部署审阅和客户端生成使用。运行中的 `/openapi.json` 是服务端运行时来源；修改 FastAPI 路由或请求/响应模型后，应重新生成并检查差异。

该契约只描述接口和数据模型，不包含适配器密钥、管理员密钥、学生资料或生产地址。它不代表真实 Open WebUI Tools 注册、真实 OCR/模型提供商或正式环境切换已完成。

2026-11-04 当前源码契约为66 paths /24 schemas、schema11：在首批schema10/61/22基础上增加受限变式审核/撤销与可投放版本列表；learner-context支持显式清空选择。P0 当前仍运行旧 schema 7 / 56 paths 快照，本轮没有更新或复验它。

重新生成：

```bash
python3 - <<'PY'
import json
import tempfile
from pathlib import Path
from learning_service.app import create_app
from learning_service.config import Settings
with tempfile.TemporaryDirectory(prefix='dd-local-openapi-') as directory:
    p = Path(directory)
    contract = create_app(Settings(p, p / 'learning.db', p / 'attachments', '', '', False)).openapi()
Path('docs/contracts/openapi-v1.json').write_text(
    json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
    encoding='utf-8',
)
PY
```
