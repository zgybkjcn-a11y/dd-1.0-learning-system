"""Add exact upper-subject mappings after reviewing installed questions."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from learning_service.chapter_practice import bank as chapter_bank


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "learning_service/data/family_subject_coverage_plan_v14.json"
DESTINATION = ROOT / "learning_service/data/family_subject_coverage_plan_v15.json"
SOURCE_SHA256 = "45bb12b5d61921331f8c6cde1d9576ba5fc5463c26061e31ed9a2efb6a03c62c"


def canonical_sha(question):
    raw = json.dumps(question, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
    raise ValueError("subject v14 base changed")
if DESTINATION.exists():
    raise FileExistsError(DESTINATION)

data = deepcopy(json.loads(SOURCE.read_bytes()))
data["version"] = "subject-coverage-v15-upper-subject-mapping-review-2026-11-12"
rows = {row["id"]: row for row in data["rows"]}
questions = chapter_bank()


def append(row_id, question_id, family, rationale):
    row = rows[row_id]
    question = questions.get(question_id)
    if question is None or (question["book_id"], question["chapter_id"]) != (row["book_id"], row["chapter_id"]):
        raise ValueError(f"question scope mismatch: {row_id} <- {question_id}")
    if row.get("assessment_modes", {}).get("check") != "bounded":
        raise ValueError(f"automatic mapping is not bounded: {row_id}")
    if any(mapping["question_version_id"] == question_id and mapping["task"] == "check"
           for mapping in row["mappings"]):
        raise ValueError(f"duplicate requirement mapping: {row_id} <- {question_id}")
    row["mappings"].append({
        "question_version_id": question_id,
        "question_sha256": canonical_sha(question),
        "task": "check",
        "role": "direct",
        "family": family,
        "rationale": rationale,
    })


def promote(row_id, question_id, rationale):
    row = rows[row_id]
    mapping = next((item for item in row["mappings"]
                    if item["question_version_id"] == question_id and item["task"] == "check"), None)
    if mapping is None or mapping.get("role") != "supporting":
        raise ValueError(f"expected one supporting mapping to promote: {row_id} <- {question_id}")
    if row.get("assessment_modes", {}).get("check") != "bounded":
        raise ValueError(f"automatic mapping is not bounded: {row_id}")
    mapping["role"] = "direct"
    mapping["rationale"] = rationale


for row_id, question_id, family, rationale in (
    ("ethics-g2-upper:1:safety", "family-chapter-ethics-g2-upper-1-03-v1",
     "ethics-g2-upper:1:safety:lost-and-seek-help",
     "题目设置与家人走散的情境，要求选择在安全处向工作人员求助，直接核对本项指定的安全求助方式。"),
    ("history-g7-upper:1:civilization", "family-chapter-history-g7-upper-1-upper_variety-second-v1",
     "history-g7-upper:1:civilization:compare-site-evidence",
     "题目并列河姆渡与半坡的作物、工具和居住遗迹，要求从多处材料判断农业活动及遗址差异。"),
    ("biology-g7-upper:2:plant", "family-chapter-biology-g7-upper-2-upper_variety-second-v1",
     "biology-g7-upper:2:plant:compare-cell-structures",
     "题目比较动植物细胞中的细胞膜、细胞核和植物细胞壁，直接核对共有结构与植物典型结构。"),
    ("biology-g7-upper:5:fish", "family-chapter-biology-g7-upper-5-upper_variety-animal-classify-v1",
     "biology-g7-upper:5:fish:gills-fins-and-habitat",
     "题目用鳃、鳍和水生环境判断鱼类，并与水生哺乳动物对照，直接覆盖本项限定特征。"),
    ("biology-g7-upper:6:bacteria", "family-chapter-biology-g7-upper-6-upper_variety-microbes-v1",
     "biology-g7-upper:6:bacteria:cell-structure-compare",
     "题目直接比较细菌和酵母菌有无成形细胞核，并否定细胞结构与可见性混淆。"),
):
    append(row_id, question_id, family, rationale)

promote(
    "history-g7-upper:2:reform", "family-chapter-history-g7-upper-2-upper_variety-second-v1",
    "题目要求把鼓励耕织联系到生产激励，并识别军功授爵的条件，直接对应变法措施与生产发展。",
)
promote(
    "geography-g7-upper:9:application", "family-chapter-geography-g7-upper-9-challenge_variety-091-v1",
    "题目给出更新后的实线/虚线图例并要求重选路线，直接核对依据当前图例而不沿用旧路线。",
)

raw = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
DESTINATION.write_bytes(raw)
print(json.dumps({
    "version": data["version"],
    "sha256": hashlib.sha256(raw).hexdigest(),
    "added_direct_mappings": 5,
    "promoted_mappings": 2,
}, ensure_ascii=False))
