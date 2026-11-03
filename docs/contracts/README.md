# DD-1.0 V1 OpenAPI 契约

`openapi-v1.json` 是由 `learning_service.app.create_app().openapi()` 生成的版本化接口快照，供交接、隔离部署审阅和客户端生成使用。运行中的 `/openapi.json` 是服务端运行时来源；修改 FastAPI 路由或请求/响应模型后，应重新生成并检查差异。

该契约只描述接口和数据模型，不包含适配器密钥、管理员密钥、学生资料或生产地址。它不代表真实 Open WebUI Tools 注册、真实 OCR/模型提供商或正式环境切换已完成。

重新生成：

```bash
python3 - <<'PY'
import json
from pathlib import Path
from learning_service.app import create_app
contract = create_app().openapi()
Path('docs/contracts/openapi-v1.json').write_text(
    json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
    encoding='utf-8',
)
PY
```
