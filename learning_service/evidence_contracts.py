"""Versioned excerpt/page responses and legacy scope shapes; pure data contracts."""
from __future__ import annotations

from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class TextbookChapter(Contract):
    id: str
    title: str
    printed_page: int = Field(ge=1, le=999)
    page_start: int = Field(ge=1, le=999)
    page_end: int = Field(ge=1, le=999)


class TextbookCapabilities(Contract):
    """What the deployed data supports for this book; derived, never asserted."""
    page_reading: bool
    keyword_search: bool
    installed_questions: int = Field(ge=0)
    mapped_questions: int = Field(ge=0)
    knowledge_mapping: Literal['local_sample', 'none']
    note: str


class TextbookBook(Contract):
    id: str
    grade: Literal[2, 7]
    semester: str
    subject: str
    subject_title: str
    title: str
    edition: str
    verified_on: str
    file_id: str
    collection: str
    search_available: bool = True
    reader_url: str | None = None
    capabilities: TextbookCapabilities | None = None
    chapters: list[TextbookChapter]


class TextbookSubject(Contract):
    id: str
    title: str
    available: bool
    notice: str


class TextbookCatalogue(Contract):
    items: list[TextbookBook]
    subjects: list[TextbookSubject]
    grade_notice: str


class TextbookScopeResponse(Contract):
    book: TextbookBook
    chapter: TextbookChapter
    query: str
    mode: Literal['browse', 'search']
    page_offset: int = Field(ge=0)


class PageEvidence(Contract):
    schema_id: Literal['dd-textbook-page-evidence-v1'] = Field(alias='schema')
    kind: Literal['page_location']
    evidence_id: str = Field(pattern=r'^dd-page-[a-f0-9]{64}$')
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
    review_status: Literal['location_only']
    quote_status: Literal['unavailable']
    supports_textbook_answer: Literal[False]
    eligible_as_grading_basis: Literal[False]


class PageReference(Contract):
    text: str = Field(max_length=1400)
    pdf_page: int = Field(ge=1, le=999)
    printed_page: int = Field(ge=1, le=999)
    content_title: str
    book_title: str
    review_status: Literal['reference_only']
    evidence: PageEvidence
    page_image_path: str


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
    items: list[PageReference] = Field(max_length=4)
    notice: str
    passage_result: PassageResult


TextbookSearchResponse = Annotated[PassageSearchResponse | TextbookScopeResponse, Field(discriminator='mode')]
