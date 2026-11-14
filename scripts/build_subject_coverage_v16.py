"""Review same-chapter upper-subject candidates against bounded requirements."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from learning_service.chapter_practice import bank as chapter_bank


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "learning_service/data/family_subject_coverage_plan_v15.json"
DESTINATION = ROOT / "learning_service/data/family_subject_coverage_plan_v16.json"
SOURCE_SHA256 = "96961311b7316e8cc1c0baa9b1a9280d8c9eec57e4415afc78128cc47266c938"


def canonical_sha(question):
    raw = json.dumps(question, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
    raise ValueError("subject v15 base changed")
if DESTINATION.exists():
    raise FileExistsError(DESTINATION)

data = deepcopy(json.loads(SOURCE.read_bytes()))
data["version"] = "subject-coverage-v16-upper-subject-candidate-review-2026-11-12"
rows = {row["id"]: row for row in data["rows"]}
questions = chapter_bank()


def append(row_id, question_id, family, role, rationale):
    row = rows[row_id]
    question = questions.get(question_id)
    if question is None or (question["book_id"], question["chapter_id"]) != (row["book_id"], row["chapter_id"]):
        raise ValueError(f"question scope mismatch: {row_id} <- {question_id}")
    if row.get("assessment_modes", {}).get("check") != "bounded":
        raise ValueError(f"automatic mapping is not bounded: {row_id}")
    if role not in ("direct", "supporting"):
        raise ValueError(f"invalid mapping role: {role}")
    if any(mapping["question_version_id"] == question_id and mapping["task"] == "check"
           for mapping in row["mappings"]):
        raise ValueError(f"duplicate requirement mapping: {row_id} <- {question_id}")
    row["mappings"].append({
        "question_version_id": question_id,
        "question_sha256": canonical_sha(question),
        "task": "check",
        "role": role,
        "family": family,
        "rationale": rationale,
    })


def promote(row_id, question_id, family, rationale):
    row = rows[row_id]
    mapping = next((item for item in row["mappings"]
                    if item["question_version_id"] == question_id and item["task"] == "check"), None)
    if mapping is None or mapping.get("role") != "supporting":
        raise ValueError(f"expected one supporting mapping to promote: {row_id} <- {question_id}")
    if row.get("assessment_modes", {}).get("check") != "bounded":
        raise ValueError(f"automatic mapping is not bounded: {row_id}")
    mapping["role"] = "direct"
    mapping["family"] = family
    mapping["rationale"] = rationale


promote(
    "ethics-g7-upper:4:setback", "family-chapter-ethics-g7-upper-4-challenge_variety-076-v1",
    "ethics-g7-upper:4:evidence-based-action-plan",
    "题目给出具体失利、难度差异和订正记录，要求排除过度归因并选择可执行的订正与错因追踪计划。",
)
promote(
    "history-g7-upper:3:recovery", "family-chapter-history-g7-upper-3-upper_variety-policies-v1",
    "history-g7-upper:3:policy-purpose-matching",
    "题目把汉初休养生息与恢复生产的目标明确相连，直接核对本项要求的政策作用。",
)
promote(
    "history-g7-upper:6:cause", "family-chapter-history-g7-upper-6-challenge_variety-082-v1",
    "history-g7-upper:6:time-order-and-confounders",
    "题目依据年表确认先后，再检查同时变化的关卡和集市，直接区分时间相邻与因果证据。",
)
promote(
    "biology-g7-upper:3:plantlevels", "family-chapter-biology-g7-upper-3-upper_variety-second-v1",
    "biology-g7-upper:3:identify-plant-organ-from-structure",
    "题目依据果实由不同组织构成判断其为器官，并与人体系统层次作对照，直接检查植物器官判断。",
)
promote(
    "biology-g7-upper:5:mammal", "family-chapter-biology-g7-upper-5-upper_variety-animal-classify-v1",
    "biology-g7-upper:5:classify-from-diagnostic-traits",
    "题目依据鳃鳍及胎生哺乳特征区分鱼类和哺乳类，并明确栖息环境相同不代表同类。",
)
append(
    "geography-g7-upper:1:scale", "family-chapter-geography-g7-upper-1-challenge_variety-083-v1",
    "geography-g7-upper:1:bound-place-and-time",
    "direct",
    "题目要求比较同地点、同一上学时段的连续记录，并将结论限制在已观测的日期、地点和时段。",
)
append(
    "geography-g7-upper:4:change", "family-chapter-geography-g7-upper-4-02-v1",
    "geography-g7-upper:4:infer-past-environment-from-fossils",
    "direct",
    "题目把海生化石作为过去环境的线索，同时排除由单件证据推出完整抬升过程，直接区分证据与解释范围。",
)
append(
    "geography-g7-upper:4:change", "family-chapter-geography-g7-upper-4-03-v1",
    "geography-g7-upper:4:combine-change-evidence",
    "supporting",
    "题目只选择结合多种证据的方法，没有把具体观察与解释逐项区分，保留辅助。",
)
append(
    "biology-g7-upper:5:mammal", "family-chapter-biology-g7-upper-5-02-v1",
    "biology-g7-upper:5:classify-from-diagnostic-traits",
    "direct",
    "题目用肺呼吸、胎生和哺乳特征判断水生鲸属于哺乳动物，直接示范分类不能只依据环境。",
)
append(
    "biology-g7-upper:5:mammal", "family-chapter-biology-g7-upper-5-03-v1",
    "biology-g7-upper:5:classify-from-diagnostic-traits",
    "direct",
    "题目要求否定仅凭飞行能力把蝙蝠和鸟归为一类，并指出应核对身体结构与生殖特征。",
)

for row_id, question_id, family, rationale in (
    ("ethics-g7-upper:2:teacher", "family-chapter-ethics-g7-upper-2-upper_variety-scenario-v1",
     "ethics-g7-upper:2:evidence-based-disagreement",
     "题目核对资料来源并针对观点沟通，但情境是同伴合作，没有具体师生分歧，保留辅助。"),
    ("ethics-g7-upper:2:group", "family-chapter-ethics-g7-upper-2-03-v1",
     "ethics-g7-upper:2:negotiate-shared-work",
     "题目考查按能力和时间协商分工，但没有要求比较不同方案对个人和集体的影响，保留辅助。"),
    ("history-g7-upper:2:culture", "family-chapter-history-g7-upper-2-02-v1",
     "history-g7-upper:2:identify-oracle-bone-material",
     "题目核对甲骨文材料这一局部事实，没有比较青铜类别、年代与可支持的历史信息，保留辅助。"),
    ("history-g7-upper:4:reform", "family-chapter-history-g7-upper-4-03-v1",
     "history-g7-upper:4:analyze-reform-impact-method",
     "题目只选择分析北魏改革影响的方法，没有依据具体措施判断交融影响，保留辅助。"),
    ("geography-g7-upper:5:rain", "family-chapter-geography-g7-upper-5-upper_variety-second-v1",
     "geography-g7-upper:5:compare-two-month-precipitation",
     "题目比较一月与七月的月降水量差，没有求季节总量，保留辅助。"),
    ("geography-g7-upper:6:culture", "family-chapter-geography-g7-upper-6-03-v1",
     "geography-g7-upper:6:respect-cultural-differences",
     "题目检查尊重差异与避免以偏概全，但没有依据材料比较文化表现，保留辅助。"),
):
    append(row_id, question_id, family, "supporting", rationale)

raw = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
DESTINATION.write_bytes(raw)
print(json.dumps({
    "version": data["version"],
    "sha256": hashlib.sha256(raw).hexdigest(),
    "promoted_mappings": 5,
    "added_direct_mappings": 4,
    "added_supporting_mappings": 7,
}, ensure_ascii=False))
