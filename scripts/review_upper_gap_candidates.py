"""Export the frozen upper-gap candidates and separate installed/proposed evidence.

Reads local content only. Temporarily exposes candidates to the coverage renderer
in this process; never changes the runtime registry or opens a database.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from html import escape
import json
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from learning_service import chapter_practice as chapter, practice_coverage, subject_coverage
from learning_service.textbooks import learning_scope, PDF_SHA256
from scripts.build_upper_gap_candidates import BATCH, DESTINATION, ROOT, build

BASE_REVIEW = ROOT / "learning_data/verification/upper-subject-review-20261112/review-v17"
AVAILABLE = ROOT / "learning_data/verification/math-single-action-20261112/available-ids.json"
SUBJECT = ROOT / "learning_service/data/family_subject_coverage_plan_v16.json"
EXPECTED_SUBJECT_SHA = "f3861070f1081833a47bf5a2cca5dedb714de44f0fc8878eea85ec2d9490189a"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def canonical(q):
    return sha(json.dumps(q, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def proposal():
    raw = DESTINATION.read_bytes()
    if json.loads(raw) != build():
        raise ValueError("candidate differs from reviewed authoring source")
    if sha(SUBJECT.read_bytes()) != EXPECTED_SUBJECT_SHA:
        raise ValueError("subject-v16 base changed")
    if BATCH in chapter.BATCHES:
        raise ValueError("candidate must remain unregistered")
    _, _, questions = chapter._parse(raw)
    decisions = json.loads((BASE_REVIEW / "candidate-review-decisions.json").read_bytes())
    gaps = {r["point_id"]: r for r in decisions["items"]
            if r["after_category"] in ("no_mapping", "supporting_only")}
    if len(gaps) != 20 or Counter(q["knowledge"]["point_id"] for q in questions.values()) != Counter(gaps.keys()):
        raise ValueError("exactly one candidate per reviewed gap is required")
    before = json.loads(SUBJECT.read_bytes())
    after = deepcopy(before)
    after["version"] = "subject-coverage-v17-upper-gap-proposal-2026-11-13"
    after["candidate_only"] = True
    rows = {r["id"]: r for r in after["rows"]}
    for q in questions.values():
        k = q["knowledge"]
        rows[k["point_id"]]["mappings"].append({
            "question_version_id": q["id"], "question_sha256": canonical(q),
            **{name: k[name] for name in ("task", "role", "family", "rationale")}})
    return questions, gaps, before, after


def reports(questions, before, after):
    snapshot = json.loads(AVAILABLE.read_bytes())
    if sha(AVAILABLE.read_bytes()) != "853ed5521fc5bc134575c6151e2b76937dae968d7aeedd8e514f847cceeaa15b":
        raise ValueError("installed ID snapshot changed")
    ids = {g: set(snapshot["available_ids"][str(g)]) for g in (2, 7)}
    installed_before = [practice_coverage.render_report(before, f"math-g{g}-v1", ids[g]) for g in (2, 7)]
    # Scoped in-memory registry for the existing renderer's identity checks only.
    with patch.dict(chapter.BATCHES, {BATCH: sha(DESTINATION.read_bytes())}):
        installed_after = [practice_coverage.render_report(after, f"math-g{g}-v1", ids[g]) for g in (2, 7)]
        proposed = [practice_coverage.render_report(after, f"math-g{g}-v1",
                    ids[g] | {q["id"] for q in questions.values() if q["grade"] == g}) for g in (2, 7)]
    assert [r["items"] for r in installed_before] == [r["items"] for r in installed_after]
    return installed_before, installed_after, proposed


def export(destination):
    questions, gaps, before, after = proposal()
    installed_before, installed_after, proposed = reports(questions, before, after)
    destination.mkdir(parents=True, exist_ok=False)
    write(destination / "candidates.json", json.loads(DESTINATION.read_bytes()))
    write(destination / "subject-v17-proposal.json", after)
    write(destination / "installed-before.json", installed_before)
    write(destination / "installed-with-proposal.json", installed_after)
    write(destination / "candidate-inclusive.json", proposed)
    flat = lambda rs: {r["id"]: r for report in rs for r in report["items"]}
    a, b = flat(installed_before), flat(proposed)
    def check(row):
        return next(t for t in row["tasks"] if t["id"] == "check")
    diff, evidence = [], []
    for q in questions.values():
        point = q["knowledge"]["point_id"]
        old, new = check(a[point]), check(b[point])
        diff.append({"point_id": point, "requirement": gaps[point]["requirement"],
            "question_version_id": q["id"], "question_sha256": canonical(q),
            "formal_before_category": gaps[point]["after_category"],
            "formal_after": old, "candidate_inclusive_after": new,
            "role": q["knowledge"]["role"], "family": q["knowledge"]["family"],
            "review": q["review"], "remaining_gap":
                "实际提出/表达/操作尚无证据，继续辅助；人工任务未观察。" if q["knowledge"]["role"] == "supporting"
                else "新增一个直接题型族，仍未达到两个不同题型族的编辑目标；人工任务另核。",
            "prior_same_scope_review_reused": True})
        _, scope = learning_scope(f"math-g{q['grade']}-v1", q["book_id"], q["chapter_id"])
        path = ROOT / "learning_data/textbooks/pep-current-20261105" / (q["book_id"] + ".pdf")
        digest = sha(path.read_bytes())
        assert digest == PDF_SHA256[q["book_id"]]
        evidence.append({"question_version_id": q["id"], "book_id": q["book_id"],
            "pdf_path": str(path.relative_to(ROOT)), "pdf_sha256": digest,
            "chapter_id": scope["id"], "chapter_title": scope["title"],
            "printed_pages": q["source"]["topic_printed_pages"],
            "pdf_pages": [p + scope["page_start"] - scope["printed_page"] for p in q["source"]["topic_printed_pages"]],
            "cross_chapter_reference": {"printed_page": 48, "pdf_page": 57, "purpose": "单一变量控制"}
                if point == "biology-g7-upper:1:observation" else None,
            "evidence_limit": q["source"]["evidence_limit"],
            "source_review_method": "local_original_PDF_native_text_and_page_location_check_no_OCR",
            "license": "题干、图表和反馈项目原创；PDF仅作本地核对依据，未复制教材图片或练习。"})
    write(destination / "coverage-diff.json", diff)
    write(destination / "source-evidence.json", evidence)
    write(destination / "manual-tasks.json", [dict(question_id=q["id"], point_id=q["knowledge"]["point_id"], **q["manual_followup"])
                                               for q in questions.values() if "manual_followup" in q])
    counts = lambda rs: dict(Counter(t["status"] for report in rs for r in report["items"] for t in r["tasks"]))
    summary = {"candidate_questions": len(questions), "response_fields": sum(len(q["responses"]) for q in questions.values()),
        "roles": dict(Counter(q["knowledge"]["role"] for q in questions.values())),
        "by_book": dict(Counter(q["book_id"] for q in questions.values())),
        "formal_snapshot_questions": 1145, "formal_snapshot_by_grade": {"2": 418, "7": 727},
        "formal_coverage_unchanged": counts(installed_before), "candidate_inclusive": counts(proposed),
        "new_configured_requirements": 0, "manual_followups": 4, "local_bank_registered": False,
        "teacher_reviewed": False, "curriculum_standard_crosscheck": "pending", "student_calibrated": False,
        "runtime_subject_version": "subject-coverage-v5-language-gaps-2026-11-12",
        "local_base": "math-v15 / subject-v16", "proposal_version": after["version"],
        "production_database_accessed": False, "production_import_or_deployment": False,
        "c01_called_or_started": False, "external_model_ocr_embedding_calls": 0,
        "phone": "deferred_by_user", "limitations": [
            "四项只形成辅助题和人工任务，未改变原bounded/human分类。",
            "另外16项各补一个直接族，全部仍为partial；不能冒称20项完全补齐。",
            "下册及新增教材不在这20题的覆盖统计中。",
            "审核为同一助手内容复核和独立算术约束检查，不是独立教师签署或盲测。"]}
    write(destination / "summary.json", summary)
    style = """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>上册20项本地候选审阅</title><style>body{font:17px/1.65 sans-serif;max-width:1000px;margin:32px auto;padding:0 24px;color:#17212b}
article{border-top:2px solid #ccd;padding:24px 0}pre{white-space:pre-wrap}table{border-collapse:collapse;width:100%;margin:12px 0}td,th{border:1px solid #99a;padding:8px;text-align:center}summary{cursor:pointer}li{margin:6px 0}.badge{background:#eef;padding:4px 8px}a{color:#145ba0}@media print{article{break-before:page}details{display:block}}</style>"""
    page = [style, "<h1>上册20项缺口 · 本地候选审阅</h1>",
        "<p>20题共74个作答项（作答项不另计题）。16题为一个直接题型族，4题仅辅助并附人工任务。未导入、未注册、未部署；教师签署与真实难度校准待完成。</p>",
        '<p><a href="coverage-diff.json">逐项覆盖差异</a> · <a href="source-evidence.json">固定原页依据</a> · <a href="manual-tasks.json">人工任务</a></p>']
    # Counts are derived, including if subsequent local drafts alter field count.
    page[2] = page[2].replace("74个", str(summary["response_fields"]) + "个")
    for q in questions.values():
        point = q["knowledge"]["point_id"]
        esc = escape
        page += [f'<article id="{esc(point)}"><h2>{esc(q["title"])}</h2>',
            f'<p class="badge">{esc(point)} · {esc(q["knowledge"]["role"])} · 正常（试用分档）</p>',
            f'<p>要求：{esc(gaps[point]["requirement"])}</p><pre>{esc(q["prompt"])}</pre>']
        if "visual" in q:
            v = q["visual"]
            page.append("<table><caption>" + esc(v["caption"]) + "</caption>")
            for i, row in enumerate(v["rows"]):
                tag = "th" if i == 0 else "td"
                page.append("<tr>" + "".join(f"<{tag}>{esc(c)}</{tag}>" for c in row) + "</tr>")
            page.append("</table>")
        page.append("<ol>")
        for f in q["responses"]:
            page.append("<li>" + esc(f["label"]))
            if f["options"]:
                page.append("<ol>" + "".join("<li>" + esc(o) + "</li>" for o in f["options"]) + "</ol>")
            page.append("</li>")
        page.append("</ol><details open><summary>答案与复核</summary>")
        answers = [f["options"][int(f["answer"]) - 1] if f["kind"] == "choice" else f["answer"] for f in q["responses"]]
        for label, value in [("答案", "；".join(answers)), ("解析", q["explanation"]),
                ("常见错误反馈", q["common_error_feedback"]), ("难度依据", q["design"]["difficulty_rationale"]),
                ("完整性复核", q["review"]["content_check"]), ("来源边界", q["source"]["evidence_limit"])]:
            page.append(f"<p><b>{label}：</b>{esc(value)}</p>")
        page.append("<p>具体书内页：" + esc(str(q["source"]["topic_printed_pages"])) + "</p></details>")
        if "manual_followup" in q:
            m = q["manual_followup"]
            page.append("<h3>另行人工核对（未观察，不自动判分）</h3><p>" + esc(m["prompt"]) + "</p><ul>" + "".join("<li>" + esc(c) + "</li>" for c in m["criteria"]) + "</ul>")
        page.append("</article>")
    page.append("</html>")
    (destination / "index.html").write_text("".join(page))
    inputs = [DESTINATION, SUBJECT, practice_coverage.PATH, AVAILABLE, BASE_REVIEW / "candidate-review-decisions.json",
              BASE_REVIEW / "installed-questions.json", ROOT / "docs/releases/current-manifest.json", Path(__file__),
              ROOT / "scripts/build_upper_gap_candidates.py"]
    write(destination / "provenance.json", {"created_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in inputs},
        "outputs": {p.name: sha(p.read_bytes()) for p in destination.iterdir() if p.is_file()},
        "reviewer": "assistant", "teacher_reviewed": False,
        "reused_review": "review-v17同章正式题决定；未重复标成未审候选",
        "note": "candidate-inclusive仅为假设候选存在时的本地预览，绝非生产安装证据。"})
    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(export(args.output), ensure_ascii=False))
