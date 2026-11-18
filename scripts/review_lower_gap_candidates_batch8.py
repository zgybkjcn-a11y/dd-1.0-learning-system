"""Export the eighth lower-book candidate batch with separate evidence.

Reads local content only. Temporarily exposes the candidate batch to the coverage
renderer in this process; never changes the runtime registry or opens a database.
Installed evidence and candidate-inclusive preview are written to separate files.
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
from learning_service import chapter_practice as chapter, practice_coverage
from learning_service.textbooks import PDF_SHA256, learning_scope
from scripts.build_lower_gap_candidates_batch8 import BATCH, DESTINATION, ROOT, build

INVENTORY = ROOT / "docs/quality/lower-knowledge-inventory-2026-11-13.json"
EXPECTED_INVENTORY_SHA = "de6cd6e59fe60a64c2dee05d2b9de6c8cb9422e7cf0dc55ad9c1be8343900de6"
SUBJECT = ROOT / "learning_service/data/family_subject_coverage_plan_v16.json"
EXPECTED_SUBJECT_SHA = "f3861070f1081833a47bf5a2cca5dedb714de44f0fc8878eea85ec2d9490189a"
SNAPSHOT = ROOT / "learning_data/verification/upper-subject-review-20261112/review-v17/installed-questions.json"
EXPECTED_SNAPSHOT_SHA = "b9a4d858786f65cbf91349ad6950e106a27313cc2ce847888b54f5dc7246c4ce"
# One inventoried bounded requirement from each remaining scope in this batch.
POINT_SCOPES = ("history-g7-lower:2", "history-g7-lower:3", "history-g7-lower:4")
EXPECTED_CANDIDATES = 4
SOURCE_INDEX = ROOT / "learning_data/verification/lower-inventory-20261113/source-evidence.json"
EXPECTED_SOURCE_INDEX_SHA = "2b7a17b84dafb385c4897d52d5acf33c68a1c43654cb97effade79d187986c91"
# Pages whose figures were checked as rendered images, not only through their text layer.
FIGURE_VERIFIED = {}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify_sources():
    raw = SOURCE_INDEX.read_bytes()
    if sha(raw) != EXPECTED_SOURCE_INDEX_SHA:
        raise ValueError("reviewed source index changed")


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def canonical(q):
    return sha(json.dumps(q, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def has_text_layer(book_id):
    """Native text presence comes from the reviewed extraction index, not a guess."""
    for row in json.loads(SOURCE_INDEX.read_bytes()):
        if row["book_id"] == book_id:
            return row["native_text_chars"] > 0
    raise ValueError("book missing from the reviewed source index: " + book_id)


def pdf_path(book_id):
    """Resolve the reviewed original from the verified source index, then re-hash it."""
    for row in json.loads(SOURCE_INDEX.read_bytes()):
        if row["book_id"] != book_id:
            continue
        path = ROOT / row["source_pdf"]
        if path.is_file() and sha(path.read_bytes()) == PDF_SHA256[book_id]:
            return path
        raise ValueError("reviewed original hash changed for " + book_id)
    raise ValueError("reviewed original not indexed for " + book_id)


def proposal():
    raw = DESTINATION.read_bytes()
    if json.loads(raw) != build():
        raise ValueError("candidate differs from reviewed authoring source")
    if sha(SUBJECT.read_bytes()) != EXPECTED_SUBJECT_SHA:
        raise ValueError("subject-v16 base changed")
    if sha(INVENTORY.read_bytes()) != EXPECTED_INVENTORY_SHA:
        raise ValueError("lower inventory changed")
    if sha(SNAPSHOT.read_bytes()) != EXPECTED_SNAPSHOT_SHA:
        raise ValueError("installed ID snapshot changed")
    verify_sources()
    registered = chapter.BATCHES.get(BATCH)
    if registered is not None and registered != sha(DESTINATION.read_bytes()):
        raise ValueError("registered candidate differs from reviewed source")
    _, _, questions = chapter._parse(raw)
    plan = json.loads(SUBJECT.read_bytes())
    inventory = json.loads(INVENTORY.read_bytes())
    scopes = {s["id"]: s for s in inventory["scopes"]}
    points = {p["id"]: p for sid, s in scopes.items() if sid in POINT_SCOPES
              for p in s["new_initial_points"]}
    if len(questions) != EXPECTED_CANDIDATES:
        raise ValueError("four eighth-batch candidates are required")
    if Counter(q["knowledge"]["point_id"] for q in questions.values()) != Counter(points.keys()):
        raise ValueError("exactly one candidate per inventoried point is required")
    before = deepcopy(plan)
    for point_id, point in points.items():
        book_id, chapter_id, _ = point_id.split(":")
        scope = scopes[f"{book_id}:{chapter_id}"]
        if book_id not in plan["pdf_sha256"]:
            before["pdf_sha256"][book_id] = PDF_SHA256[book_id]
        role = next(q["knowledge"]["role"] for q in questions.values()
                    if q["knowledge"]["point_id"] == point_id)
        before["rows"].append({
            "id": point_id, "book_id": book_id, "chapter_id": chapter_id,
            "title": point["title"], "printed_page": point["source_printed_pages"][0],
            "location_kind": "topic_location_not_quote",
            "requirements": {"check": point["bounded_candidate_action"]},
            # Manual observation stays human unless a direct automated family exists.
            "assessment_modes": {"check": "human" if role == "supporting" else "bounded"},
            "mappings": [],
            "manual_task": {"title": point["title"] + "：独立表达或操作",
                            "automatically_graded": False,
                            "prompt": point["manual_task"]["prompt"],
                            "criteria": point["manual_task"]["criteria"]},
            "candidate_only": True, "source_printed_range": scope["printed_range"],
            "catalogue_scope_kind": scope["kind"]})
    before["task_labels"] = {**before["task_labels"], "check": "完整有界要求核对"}
    before["version"] = "subject-coverage-v25-lower-eighth-batch-proposal-2026-11-14"
    before["candidate_only"] = True
    after = deepcopy(before)
    rows = {r["id"]: r for r in after["rows"]}
    for q in questions.values():
        k = q["knowledge"]
        rows[k["point_id"]]["mappings"].append({
            "question_version_id": q["id"], "question_sha256": canonical(q),
            **{name: k[name] for name in ("task", "role", "family", "rationale")}})
    return questions, points, before, after


def reports(questions, before, after):
    """Installed evidence is unchanged; candidate coverage is shown separately."""
    installed_ids = {q["id"] for q in json.loads(SNAPSHOT.read_bytes())}
    candidate_ids = {q["id"] for q in questions.values()}
    assert len(installed_ids) == 1145 and not (installed_ids & candidate_ids)
    original = {r["id"] for r in json.loads(SUBJECT.read_bytes())["rows"]}
    digest = sha(DESTINATION.read_bytes())
    with patch.dict(chapter.BATCHES, {BATCH: digest}):
        installed = [practice_coverage.render_report(before, f"math-g{g}-v1", installed_ids)
                     for g in (2, 7)]
        proposed = [practice_coverage.render_report(after, f"math-g{g}-v1",
                                                    installed_ids | candidate_ids)
                    for g in (2, 7)]
    flat = lambda rs: {r["id"]: r for report in rs for r in report["items"]}
    a, b = flat(installed), flat(proposed)
    # Adding candidate-only rows must not change any pre-existing requirement.
    assert original <= set(a) and original <= set(b)
    for row_id in sorted(original):
        assert a[row_id]["tasks"] == b[row_id]["tasks"], row_id
    assert set(a) == set(b)
    return installed, proposed


def export(destination):
    questions, points, before, after = proposal()
    installed, proposed = reports(questions, before, after)
    destination.mkdir(parents=True, exist_ok=False)
    write(destination / "candidates.json", json.loads(DESTINATION.read_bytes()))
    write(destination / "subject-v25-proposal.json", after)
    write(destination / "installed-before.json", installed)
    write(destination / "candidate-inclusive.json", proposed)
    flat = lambda rs: {r["id"]: r for report in rs for r in report["items"]}
    a, b = flat(installed), flat(proposed)
    diff, evidence = [], []
    for q in questions.values():
        point = q["knowledge"]["point_id"]
        book_id, chapter_id, _ = point.split(":")
        old = next(t for t in a[point]["tasks"] if t["id"] == "check")
        new = next(t for t in b[point]["tasks"] if t["id"] == "check")
        _, scope = learning_scope(f"math-g{q['grade']}-v1", book_id, chapter_id)
        path = pdf_path(book_id)
        diff.append({"point_id": point, "requirement": points[point]["bounded_candidate_action"],
                     "question_version_id": q["id"], "question_sha256": canonical(q),
                     "installed_before": old, "candidate_inclusive_after": new,
                     "role": q["knowledge"]["role"], "family": q["knowledge"]["family"],
                     "review": q["review"],
                     "remaining_gap": ("新增一个直接题型族，未达两种题型族的编辑目标；人工任务另核。")})
        evidence.append({"question_version_id": q["id"], "book_id": book_id,
                         "pdf_path": str(path.relative_to(ROOT)),
                         "pdf_sha256": PDF_SHA256[book_id],
                         "chapter_id": scope["id"], "chapter_title": scope["title"],
                         "printed_pages": q["source"]["topic_printed_pages"],
                         "pdf_pages": [p + scope["page_start"] - scope["printed_page"]
                                       for p in q["source"]["topic_printed_pages"]],
                         "source_review_method": ("local_page_image_view_no_OCR"
                                                  if not has_text_layer(book_id)
                                                  else "local_original_PDF_native_text_no_OCR"),
                         "text_layer": has_text_layer(book_id),
                         "figure_review": "local_page_image_view_no_OCR"
                                          if point in FIGURE_VERIFIED else "unverified",
                         "evidence_limit": q["source"]["evidence_limit"],
                         "license": "题干、材料、数据与反馈项目原创；PDF仅作本地核对依据，"
                                    "未复制教材图片或练习。"})
    write(destination / "coverage-diff.json", diff)
    write(destination / "source-evidence.json", evidence)
    write(destination / "manual-tasks.json", [
        dict(question_id=q["id"], point_id=q["knowledge"]["point_id"], **q["manual_followup"])
        for q in questions.values() if "manual_followup" in q])
    counts = lambda rs: dict(Counter(t["status"] for report in rs for r in report["items"]
                                     for t in r["tasks"]))
    summary = {"candidate_questions": len(questions),
               "candidate_points": len(points),
               "response_fields": sum(len(q["responses"]) for q in questions.values()),
               "roles": dict(Counter(q["knowledge"]["role"] for q in questions.values())),
               "by_book": dict(Counter(q["book_id"] for q in questions.values())),
               "point_scopes": list(POINT_SCOPES),
               "installed_evidence": counts(installed),
               "candidate_inclusive": counts(proposed),
               "new_configured_requirements": 0,
               "formal_snapshot_questions": 1145,
               "formal_snapshot_by_grade": {"2": 418, "7": 727},
               "lower_inventory": {"books": 10, "catalogue_scopes": 75,
                                   "new_initial_points": 68,
                                   "sha256": EXPECTED_INVENTORY_SHA},
               "figure_verified_items": {
                   point: {"printed_pages": pages,
                           "method": "local_page_image_view_no_OCR",
                           "note": "以渲染后的原页图像核对图例、地图或分布图，不使用 OCR。"}
                   for point, pages in FIGURE_VERIFIED.items()},
               "local_bank_registered": BATCH in chapter.BATCHES, "teacher_reviewed": False,
               "curriculum_standard_crosscheck": "pending", "student_calibrated": False,
               "runtime_subject_version": "subject-coverage-v5-language-gaps-2026-11-12",
               "local_base": "math-v15 / subject-v16",
               "proposal_version": after["version"],
               "production_database_accessed": False, "production_import_or_deployment": False,
               "c01_called_or_started": False, "external_model_ocr_embedding_calls": 0,
               "phone": "deferred_by_user", "limitations": [
                   "四题只覆盖三个范围各一处有界要求，不是这些单元的史事穷尽。",
                   "七下历史只考教材给出的纪年、措施、史料出处与节日表述；讲述、史料互证与"
                   "节日调查仍归人工任务且未观察。",
                   "北宋与明朝两题只取教材明确写出的年份与措施，不评价历史人物功过。",
                   "节日题只以第 128 页的材料为限，不把当代习俗外推到全部历史时期。",
                   "四题均为直接题型族，但每项只给一个族，未达两种题型族的编辑目标。",
                   "审核为同一助手内容复核与独立算术约束检查，不是独立教师签署或盲测。"]}
    write(destination / "summary.json", summary)
    style = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
             '<meta name="viewport" content="width=device-width,initial-scale=1">'
             '<title>下册第八批本地候选审阅</title><style>body{font:17px/1.65 sans-serif;'
             'max-width:1000px;margin:32px auto;padding:0 24px;color:#17212b}'
             'article{border-top:2px solid #ccd;padding:24px 0}pre{white-space:pre-wrap}'
             'table{border-collapse:collapse;width:100%;margin:12px 0}'
             'td,th{border:1px solid #99a;padding:8px;text-align:center}'
             'summary{cursor:pointer}li{margin:6px 0}.badge{background:#eef;padding:4px 8px}'
             'a{color:#145ba0}@media print{article{break-before:page}details{display:block}}'
             '</style>')
    page = [style, "<h1>下册第八批（七下历史第二单元、第三单元与活动课/学史方法）· 本地候选审阅</h1>",
            f"<p>{len(questions)}题共{summary['response_fields']}个作答项"
            f"（作答项不另计题）。{summary['roles'].get('direct', 0)}题为直接题型族，"
            f"{summary['roles'].get('supporting', 0)}题仅辅助并附人工任务。"
            "未导入、未注册、未部署；教师签署与真实难度校准待完成。</p>",
            '<p><a href="coverage-diff.json">逐项覆盖差异</a> · '
            '<a href="source-evidence.json">固定原页依据</a> · '
            '<a href="manual-tasks.json">人工任务</a></p>']
    for q in questions.values():
        point = q["knowledge"]["point_id"]
        page += [f'<article id="{escape(point)}"><h2>{escape(q["title"])}</h2>',
                 f'<p class="badge">{escape(point)} · {escape(q["knowledge"]["role"])}'
                 f' · 正常（试用分档）</p>',
                 f'<p>要求：{escape(points[point]["bounded_candidate_action"])}</p>'
                 f'<pre>{escape(q["prompt"])}</pre>']
        if "visual" in q:
            v = q["visual"]
            page.append("<table><caption>" + escape(v["caption"]) + "</caption>")
            for i, row in enumerate(v["rows"]):
                tag = "th" if i == 0 else "td"
                page.append("<tr>" + "".join(f"<{tag}>{escape(c)}</{tag}>" for c in row) + "</tr>")
            page.append("</table>")
        page.append("<ol>")
        for f in q["responses"]:
            page.append("<li>" + escape(f["label"]))
            if f["options"]:
                page.append("<ol>" + "".join("<li>" + escape(o) + "</li>" for o in f["options"]) + "</ol>")
            page.append("</li>")
        page.append("</ol><details open><summary>答案与复核</summary>")
        answers = [f["options"][int(f["answer"]) - 1] if f["kind"] == "choice" else f["answer"]
                   for f in q["responses"]]
        for label, value in [("答案", "；".join(answers)), ("解析", q["explanation"]),
                             ("常见错误反馈", q["common_error_feedback"]),
                             ("难度依据", q["design"]["difficulty_rationale"]),
                             ("完整性复核", q["review"]["content_check"]),
                             ("来源边界", q["source"]["evidence_limit"])]:
            page.append(f"<p><b>{label}：</b>{escape(value)}</p>")
        page.append("<p>具体书内页：" + escape(str(q["source"]["topic_printed_pages"]))
                    + "</p></details>")
        if "manual_followup" in q:
            m = q["manual_followup"]
            page.append("<h3>另行人工核对（未观察，不自动判分）</h3><p>" + escape(m["prompt"])
                        + "</p><ul>"
                        + "".join("<li>" + escape(c) + "</li>" for c in m["criteria"]) + "</ul>")
        page.append("</article>")
    page.append("</html>")
    (destination / "index.html").write_text("".join(page))
    inputs = [DESTINATION, SUBJECT, INVENTORY, SNAPSHOT, practice_coverage.PATH,
              ROOT / "docs/releases/current-manifest.json", Path(__file__),
              ROOT / "scripts/build_lower_gap_candidates_batch8.py"]
    write(destination / "provenance.json", {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in inputs},
        "outputs": {p.name: sha(p.read_bytes()) for p in destination.iterdir() if p.is_file()},
        "reviewer": "assistant", "teacher_reviewed": False,
        "reused_review": "下册初步清单；未重复审已完成的同章条目",
        "note": "candidate-inclusive仅为假设候选存在时的本地预览，绝非生产安装证据。"})
    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(export(args.output), ensure_ascii=False))
