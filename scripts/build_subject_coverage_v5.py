"""Create a new additive subject plan from reviewed existing and authored questions."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from learning_service.chapter_practice import bank as chapter_bank


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "learning_service/data/family_subject_coverage_plan_v4.json"
DESTINATION = ROOT / "learning_service/data/family_subject_coverage_plan_v5.json"
SOURCE_SHA256 = "5717ee871cc1b65d159ec575915e9a686f8a7473fc33b876fae2bd9ebf645fb3"


def canonical_sha(question):
    raw = json.dumps(question, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
    raise ValueError("subject v4 base changed")
if DESTINATION.exists():
    raise FileExistsError(DESTINATION)

data = deepcopy(json.loads(SOURCE.read_bytes()))
data["version"] = "subject-coverage-v5-language-gaps-2026-11-12"
rows = {row["id"]: row for row in data["rows"]}
questions = chapter_bank()


def append(row_id, question_id, family, role="direct", rationale=None):
    row = rows[row_id]
    question = questions.get(question_id)
    if question is None or (question["book_id"], question["chapter_id"]) != (row["book_id"], row["chapter_id"]):
        raise ValueError(f"question scope mismatch: {row_id} <- {question_id}")
    if any(mapping["question_version_id"] == question_id and mapping["task"] == "check" for mapping in row["mappings"]):
        raise ValueError(f"duplicate requirement mapping: {row_id} <- {question_id}")
    row["mappings"].append({
        "question_version_id": question_id,
        "question_sha256": canonical_sha(question),
        "task": "check",
        "role": role,
        "family": family,
        "rationale": rationale or "题目直接核对本项限定要求；不替代人工表达或课程复核。",
    })


def promote(row_id, question_id, rationale):
    row = rows[row_id]
    mapping = next((item for item in row["mappings"]
                    if item["question_version_id"] == question_id and item["task"] == "check"), None)
    if mapping is None or mapping.get("role") != "supporting":
        raise ValueError(f"expected one supporting mapping to promote: {row_id} <- {question_id}")
    mapping["role"] = "direct"
    mapping["rationale"] = rationale


for row_id, question_id, family, rationale in (
    ("chinese-g2-upper:3:comparison", "family-chapter-chinese-g2-upper-3-01-v1",
     "chinese-g2-upper:3:comparison:identify-compared-object",
     "题目明确询问句子把星星比作什么，题干已给出本体，答案核对喻体。"),
    ("chinese-g2-upper:5:fable", "family-chapter-chinese-g2-upper-5-02-v1",
     "chinese-g2-upper:5:fable:fact-boundary",
     "题目让学习者区分寓言中有直接依据的事实与扩大到所有屋顶的结论。"),
    ("chinese-g7-upper:3:contrast", "family-chapter-chinese-g7-upper-3-03-v1",
     "chinese-g7-upper:3:contrast:shared-dimension",
     "题目直接检验比较两处生活场景时是否从相同维度分别找证据。"),
    ("chinese-g7-upper:4:structure", "family-chapter-chinese-g7-upper-4-03-v1",
     "chinese-g7-upper:4:structure:timeline",
     "题目要求依据材料中的人生阶段顺序整理文章思路。"),
    ("chinese-g7-upper:6:satire", "family-chapter-chinese-g7-upper-6-challenge_variety-044-v1",
     "chinese-g7-upper:6:satire:words-actions-contradiction",
     "题目把角色的自我辩解与实际借羽、隐瞒行为并置，核对言行矛盾及讽刺指向。"),
):
    append(row_id, question_id, family, rationale=rationale)

promote(
    "chinese-g2-upper:8:repair", "family-chapter-chinese-g2-upper-8-challenge_variety-028-v1",
    "排序项覆盖意外、道歉补救、共同处理与结果，能直接核对事件起因经过结果；不代表开放叙事达标。",
)
promote(
    "english-g7-upper:15:collocation", "family-chapter-english-g7-upper-15-challenge_variety-065-v1",
    "题目要求把read books、play basketball等动词与名词搭配放入合适场景，直接核对本项。",
)
append(
    "english-g7-upper:15:collocation", "family-chapter-english-g7-upper-15-02-v1",
    "english-g7-upper:15:collocation:play-football-phrase",
    rationale="题目检查固定动词与名词组合play football的词组意义。",
)

for question in questions.values():
    knowledge = question.get("knowledge")
    if question.get("batch") != "subject_gaps" or not knowledge:
        continue
    if knowledge.get("role") != "direct" or knowledge.get("task") != "check":
        raise ValueError(f"new question needs an explicit direct bounded mapping: {question['id']}")
    append(knowledge["point_id"], question["id"], knowledge["family"], rationale=knowledge["rationale"])

raw = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
DESTINATION.write_bytes(raw)
print(json.dumps({
    "version": data["version"],
    "sha256": hashlib.sha256(raw).hexdigest(),
    "added_mappings": 20,
    "subject_gaps_questions": sum(q.get("batch") == "subject_gaps" for q in questions.values()),
}, ensure_ascii=False))
