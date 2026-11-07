# OpenAPI V1 契约证据

日期：2026-11-04（Asia/Shanghai）

## 产物

- 版本化契约：[docs/contracts/openapi-v1.json](../contracts/openapi-v1.json)
- 生成说明：[docs/contracts/README.md](../contracts/README.md)
- 运行时来源：FastAPI `create_app().openapi()` 与隔离服务 `/openapi.json`

## 检查

下面 56/20 是此前 schema 7 的契约证据。2026-11-04 provider/认证续跑更新当前源码快照为 **61 paths / 22 schemas** 并在临时数据库复核；P0 容器保持旧快照，未复验运行时一致。新增结果见 [`provider-auth-release-local-2026-11-04.md`](provider-auth-release-local-2026-11-04.md)。

```text
python3 - <<'PY'
import json
from pathlib import Path
p = Path('docs/contracts/openapi-v1.json')
data = json.loads(p.read_text())
assert data['info']['title'] == 'DD-1.0 Learning Service'
assert data['info']['version'] == '0.1.0'
assert '/health' in data['paths']
assert '/api/v1/import-batches/{batch_id}/analysis' in data['paths']
assert '/api/v1/agent-runs/{run_id}/steps' in data['paths']
assert '/api/v1/mistakes/manual' in data['paths']
print(len(data['paths']), len(data['components']['schemas']))
PY
56 20
```

契约包含 56 条路径和 20 个 Pydantic schema；页面修订、复核申请、裁决和手动错题录入接口均纳入快照。2026-11-03 复核确认 `create_app().openapi()` 与快照结构完全一致。接口模型不含密钥、资料内容或生产地址。契约是技术交付快照，不把真实模型 tool call、真实 OCR/provider 或正式上线写成已验证。
