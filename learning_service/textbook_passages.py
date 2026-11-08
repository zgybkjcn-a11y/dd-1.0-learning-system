"""Server-owned, opt-in excerpt service. Every read checks current material bytes.

Dates use Asia/Shanghai calendar days (UTC+08:00). valid_until is inclusive.
No public method accepts a filesystem location, historical date or learner ID.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .passage_evidence import asset, canonical, digest, load_bundle, quote_answer
from .passage_retrieval import retrieve
from .textbooks import bounded_references, learning_scope


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class ExcerptEvidence(Contract):
    schema_id: Literal['dd-textbook-excerpt-evidence-v1'] = Field(alias='schema')
    kind: Literal['assistant_reviewed_excerpt']
    evidence_id: str = Field(pattern=r'^dd-excerpt-[a-f0-9]{64}$')
    page_evidence_id: str = Field(pattern=r'^dd-page-[a-f0-9]{64}$')
    source_ref: str = Field(pattern=r'^dd-textbook-[a-f0-9]{64}$')
    book_id: str
    book_title: str
    grade: Literal[2, 7]
    subject: str
    semester: str
    edition: str
    edition_id: Literal['pep-2022-standard-current']
    pdf_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    source_binding: Literal['catalogue_sha256']
    chapter_id: str
    chapter_title: str
    printed_page: int = Field(ge=1, le=999)
    pdf_page: int = Field(ge=1, le=999)
    locator_precision: Literal['page']
    review_status: Literal['assistant_checked_excerpt']
    quote_status: Literal['layout_normalized_transcription']
    supports_textbook_answer: Literal[False]
    eligible_as_grading_basis: Literal[False]
    teacher_reviewed: Literal[False]
    fully_reviewed_page: Literal[False]
    review_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    text_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    context_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    image_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    review_revision: int = Field(ge=1)
    reviewed_on: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    valid_until: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')


class Excerpt(Contract):
    id: str
    text: str = Field(min_length=1, max_length=1400)
    context: str = Field(min_length=1, max_length=4000)
    evidence: ExcerptEvidence
    detail_path: str
    image_path: str


class PassageDetail(Contract):
    schema_id: Literal['dd-textbook-passage-detail-v1'] = Field(alias='schema')
    manifest_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    checked_on: str
    timezone: Literal['Asia/Shanghai']
    item: Excerpt


Status = Literal['reviewed_excerpts_only', 'no_evidence', 'low_relevance', 'insufficient_evidence']


class PassageScope(Contract):
    book_id: str
    chapter_id: str
    grade: Literal[2, 7]


class RankedExcerpt(Contract):
    evidence_id: str = Field(pattern=r'^dd-excerpt-[a-f0-9]{64}$')
    score: int = Field(ge=0)


class PassageCoverage(Contract):
    schema_id: Literal['dd-retrieval-coverage-v1'] = Field(alias='schema')
    method: Literal['bounded-rules-v1']
    coverage_complete: Literal[True]
    coverage_scope: Literal['loaded_reviewed_excerpts_only']
    scoped_count: int = Field(ge=0, le=40)
    candidate_count: int = Field(ge=0, le=40)
    limit: Literal[4]
    status: Status
    reason: str
    ranking: list[RankedExcerpt] = Field(max_length=4)
    display_order: list[str] = Field(max_length=4)


class PassageGrounding(Contract):
    status: Status
    can_quote_textbook: bool
    can_answer_from_textbook: Literal[False]
    eligible_as_grading_basis: Literal[False]
    message: str


class QuoteClaim(Contract):
    kind: Literal['direct_quote']
    text: str = Field(min_length=1, max_length=1400)
    evidence_id: str = Field(pattern=r'^dd-excerpt-[a-f0-9]{64}$')


class QuoteAnswer(Contract):
    claims: list[QuoteClaim] = Field(max_length=4)
    generated_answer: None


class PassageResult(Contract):
    schema_id: Literal['dd-textbook-passage-result-v1'] = Field(alias='schema')
    manifest_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    checked_on: str
    timezone: Literal['Asia/Shanghai']
    scope: PassageScope
    items: list[Excerpt] = Field(max_length=4)
    retrieval: PassageCoverage
    grounding: PassageGrounding
    answer: QuoteAnswer


class PassageSearchResponse(Contract):
    mode: Literal['passages']
    book_id: str
    chapter_id: str
    items: list[dict[str, Any]] = Field(max_length=4)
    notice: str
    passage_result: PassageResult


class PassageError(ValueError):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message
        super().__init__(code)


def current_day():
    return datetime.now(timezone(timedelta(hours=8))).date()


def unavailable():
    return PassageError(503, 'TEXTBOOK_PASSAGES_UNAVAILABLE', '片段材料校验未通过，已停止引用；请联系维护者，或清空关键词阅读原页。')


def load_current(settings):
    if not settings.textbook_passages_enabled:
        raise PassageError(404, 'TEXTBOOK_PASSAGES_DISABLED', '片段能力未开启，可清空关键词阅读原页。')
    if settings.textbook_passages_dir is None or settings.textbook_dir is None:
        raise unavailable()
    day = current_day()
    try:
        rows = load_bundle(settings.textbook_passages_dir, settings.textbook_passages_sha256,
                           settings.textbook_dir, as_of=day)
    except (OSError, ValueError, KeyError, TypeError, RecursionError, AttributeError):
        raise unavailable() from None
    return day, rows


def startup_status(settings):
    try:
        day, rows = load_current(settings)
        return {'status': 'ready', 'available_count': len(rows), 'checked_on': day.isoformat()}
    except PassageError as exc:
        return {'status': 'disabled' if exc.status == 404 else 'unavailable'}


def assert_current(settings, snapshot):
    # No availability cache: catch changed bytes, pins, dates and withdrawals
    # during retrieval/image reads. A later request always takes a new snapshot.
    if canonical_snapshot(load_current(settings)) != canonical_snapshot(snapshot):
        raise PassageError(409, 'TEXTBOOK_PASSAGE_STALE', '片段状态已变化，请重新查询；可继续阅读原页。')


def canonical_snapshot(snapshot):
    day, rows = snapshot
    return day.isoformat(), canonical(rows)


def public_item(row):
    e = row['evidence']
    path = f"/api/v1/textbooks/{e['book_id']}/passages/{e['evidence_id']}"
    return Excerpt.model_validate({k: row[k] for k in ('id', 'text', 'context', 'evidence')} |
                                 {'detail_path': path, 'image_path': path + '/image'}).model_dump(by_alias=True)


def stamp(settings, day):
    return {'manifest_sha256': settings.textbook_passages_sha256,
            'checked_on': day.isoformat(), 'timezone': 'Asia/Shanghai'}


def search(settings, curriculum, scope, query):
    # Scope is already authorized; user text must not contain a synthetic chapter prefix.
    if type(query) is not str or not query.strip() or len(query) > 120:
        raise PassageError(422, 'TEXTBOOK_SCOPE_INVALID', '片段检索词最多120字，请缩短后重试。')
    snapshot = load_current(settings)
    day, rows = snapshot
    result = retrieve(rows, curriculum, scope['book']['id'], scope['chapter']['id'], query)
    result['items'] = [public_item(p) for p in result['items']]
    result.update(schema='dd-textbook-passage-result-v1', **stamp(settings, day), answer=quote_answer(result))
    pages = [p['evidence']['pdf_page'] for p in result['items']]
    legacy = bounded_references(scope, {'documents': [[''] * len(pages)], 'metadatas': [[{
        'file_id': scope['book']['file_id'], 'page_number': page, 'edition': 'pep-2022-standard-current'
    } for page in pages]]})
    payload = {'mode': 'passages', 'book_id': scope['book']['id'], 'chapter_id': scope['chapter']['id'],
               'items': legacy['items'], 'notice': result['grounding']['message'], 'passage_result': result}
    validated = PassageSearchResponse.model_validate(payload).model_dump(by_alias=True)
    assert_current(settings, snapshot)
    return validated


def detail(settings, curriculum, book_id, evidence_id, chapter_id='', *, image=False):
    try:
        book, chapter = learning_scope(curriculum, book_id, chapter_id)
    except ValueError:
        raise PassageError(404, 'TEXTBOOK_PASSAGE_NOT_FOUND', '当前范围没有可用的这条片段，请重新查询或阅读原页。') from None
    snapshot = load_current(settings)
    day, rows = snapshot
    row = next((r for r in rows if r['evidence']['evidence_id'] == evidence_id
                and r['evidence']['book_id'] == book['id']
                and (not chapter['id'] or r['evidence']['chapter_id'] == chapter['id'])), None)
    if row is None:
        raise PassageError(404, 'TEXTBOOK_PASSAGE_NOT_FOUND', '片段已失效或不在当前范围，请重新查询或阅读原页。')
    if image:
        try:
            result = asset(settings.textbook_passages_dir, row['image_path'])
            if digest(result) != row['evidence']['image_sha256']:
                raise ValueError()
        except (OSError, ValueError):
            raise unavailable() from None
    else:
        result = PassageDetail.model_validate({'schema': 'dd-textbook-passage-detail-v1',
            **stamp(settings, day), 'item': public_item(row)}).model_dump(by_alias=True)
    assert_current(settings, snapshot)
    return result
