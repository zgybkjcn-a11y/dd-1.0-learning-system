# OpenAPI V1 契约证据

日期：2026-11-03（Asia/Shanghai）

## 产物

- 版本化契约：[docs/contracts/openapi-v1.json](../contracts/openapi-v1.json)
- 生成说明：[docs/contracts/README.md](../contracts/README.md)
- 运行时来源：FastAPI `create_app().openapi()` 与隔离服务 `/openapi.json`

## 检查

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
print(len(data['paths']), len(data['components']['schemas']))
PY
55 19
```

契约包含 55 条路径和 19 个 Pydantic schema；页面修订、复核申请和裁决接口均纳入快照。2026-11-03 复核确认 `create_app().openapi()` 与快照结构完全一致。接口模型不含密钥、资料内容或生产地址。契约是技术交付快照，不把真实模型 tool call、真实 provider 或正式上线写成已验证。
