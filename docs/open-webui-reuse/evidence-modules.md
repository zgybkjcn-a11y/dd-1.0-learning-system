# B09 首批证据模块与响应契约

本批拆分7个教材/伴学只读路由、共同读取校验与证据数据类型，保留现有授权、线协议和错误语义。`app.py`仍负责应用组装、认证依赖、中间件、写接口、工作线程及嵌入UI；本批不代表全应用模块化完成。验证见[B09独立记录](../verification/B09-evidence-modules-2026-11-08.md)。

浏览器验证另发现B05/B06已有接口没有进入网关白名单：家庭页面初始化读取工作区被404拒绝，继而无法加载教材目录。本批补齐`GET/PUT /api/v1/practice-workspace`、`GET /api/v1/attempts/{id}/collection-preview`和`POST /api/v1/attempts/{id}/collection`四个明确方法/路径。原身份、Origin/CSRF、档案版本、确认和幂等保护继续生效；其他方法/后缀仍拒绝，未扩大为通用转发。该缺口是在B08工作区已有的接入问题，原验证记录保持历史原样。

## 模块边界

| 模块 | 责任 |
| --- | --- |
| `api_types.py` | 共享`Context`和`APIError`；原`app`导入名称继续指向相同类型 |
| `evidence_contracts.py` | 原页、片段、检索结果与目录/范围响应模型；严格类型和字段集合 |
| `study_reference.py` | 参数白名单、重复参数拒绝、服务端档案固定、读取前后上下文和访问权复核 |
| `study_routes.py` | 每个应用单独创建router，注入认证/数据库/设置/档案解析依赖，不引用`app` |
| `textbook_passages.py` | 继续处理固定材料pin、当前日期/撤回检查、检索与逐字引用；旧模型导入名称作为别名保留 |

四个新模块可在空工作目录纯导入，不创建默认应用、数据库或目录，不读取环境秘密、不访问网络。依赖注入只在`create_app`显式组装时发生。生产入口`learning_service.app:app`仍维持原有默认应用行为；没有将整个`app`宣称为无副作用导入。

迁出的路由为`GET /math-references`、`GET /study-support`、`GET /textbooks`、`POST /textbooks/search`、片段详情/图片和原页图片，均保留`/api/v1`前缀。方法、路径、操作ID、请求参数和错误码保持兼容。数学参考与伴学内容响应的完整类型化、其他写接口和UI拆分留后续，不扩大本批范围。

## 契约变化

搜索响应原先允许`PassageSearchResponse | dict[str, Any]`，非法片段对象可能通过任意字典分支。现在以`mode`区分严格的`passages`与旧`browse/search`范围响应，原页引用也使用完整类型。非法模式、未知字段、伪造审核/判分资格和错误证据版本不能借宽松字典绕过响应校验。

片段仍使用原有`dd-textbook-excerpt-evidence-v1`、`dd-textbook-passage-detail-v1`和`dd-textbook-passage-result-v1`；原页仍为`dd-textbook-page-evidence-v1`。原页定位不取得片段引用或判分资格，片段也不升级为教师审核或完整页审核。

目录新增明确的课本/章节/学科模型。旧范围响应仍只返回`book/chapter/query/mode/page_offset`；不新增版本字段或改变网关转换流程。部分课本没有`reader_url`，序列化保留未设置状态，不凭空增加null；原有合法响应逐字段不变。请求体继续由原有范围校验处理，因此422错误码及参数拒绝方式保持一致。

OpenAPI仍为76条路径，模型从37增加至44；仅两条路径的响应定义与原`PassageSearchResponse.items`类型变化，其他现有schema及操作保持原样。错误数据触发服务端响应校验失败，不返回可能带错误授权声明的对象；这不代表新增业务成功状态。

## 兼容与交付

服务端共享档案切换/切走再切回、材料读取后授权撤销、片段撤回/过期、网关及Tool再次核验继续有效。目录、旧检索范围与当前片段输出均有合成契约验证；独立Tool和历史Tool只保留各自已支持的能力，不添加生成或OCR调用。

新增源码profile `reuse-runtime-evidence-modules-v1`，schema仍为13，候选共91文件。旧B07的86文件`reuse-runtime-verified-backup-v1`以及更早profile保留独立验证分支。新应用必须携带全部新模块，不能只替换`app.py`；既有历史包不改写。

本批仅本地候选，无提交/部署/正式库迁移。B07独立备份、B08外部监控（用户确认尚未配置）、B05家庭反馈、B04待解、B02真实观察与A09发布/家庭验收持续单列。下一项B10应先冻结合成性能基准范围、样本及截止口径，再依据实测决定优化；不预先承诺性能结果。
