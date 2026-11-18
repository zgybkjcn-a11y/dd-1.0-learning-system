"""Factory for seven read-only textbook/study routes; no default app or database."""
from __future__ import annotations

from functools import partial
from typing import Any
from fastapi import APIRouter, Depends, Request
from starlette.responses import Response

from .api_types import APIError, Context
from .config import Settings
from .db import Database
from .math_references import query_reference as query_math_reference
from .study_support import query_support as query_study_support
from .study_reference import read_study_reference
from .evidence_contracts import PassageDetail, TextbookCatalogue, TextbookSearchResponse
from .textbooks import (catalogue as textbook_catalogue, subject_catalogue as textbook_subjects,
                        search_scope as textbook_search_scope, page_scope as textbook_page_scope,
                        render_page as render_textbook_page)
from .textbook_capabilities import book_capabilities
from . import textbook_passages


def create_study_router(*, get_context, get_db, get_settings, learner_for) -> APIRouter:
    router = APIRouter()
    read_reference = partial(read_study_reference, learner_for=learner_for)

    @router.get("/api/v1/math-references")
    def math_references(request: Request, book_id: str = "", chapter_id: str = "",
                        question_version_id: str = "", concept_id: str = "",
                        ctx: Context = Depends(get_context), db: Database = Depends(get_db),
                        settings: Settings = Depends(get_settings)):
        """Read reviewed metadata for the authenticated, server-selected learner."""
        return read_reference(request, ctx, db, settings,
                                    {"book_id", "chapter_id", "question_version_id", "concept_id"},
                                    lambda conn, learner, curriculum, directory:
                                        query_math_reference(conn, learner, curriculum, directory, book_id=book_id,
                                                             chapter_id=chapter_id, question_version_id=question_version_id,
                                                             concept_id=concept_id))

    @router.get("/api/v1/study-support")
    def study_support(request: Request, subject: str = "", book_id: str = "", chapter_id: str = "",
                      ctx: Context = Depends(get_context), db: Database = Depends(get_db),
                      settings: Settings = Depends(get_settings)):
        """Local reading prompts and Markdown/Mermaid artifacts for current subjects."""
        return read_reference(request, ctx, db, settings, {"subject", "book_id", "chapter_id"},
                                    lambda conn, learner, curriculum, directory:
                                        query_study_support(conn, learner, curriculum, directory,
                                                            subject=subject, book_id=book_id, chapter_id=chapter_id))

    @router.get("/api/v1/textbooks", response_model=TextbookCatalogue, response_model_exclude_unset=True)
    def textbooks(ctx: Context = Depends(get_context), db: Database = Depends(get_db)):
        learner_id = learner_for(ctx, db=db)
        with db.session() as conn:
            curriculum = conn.execute('SELECT curriculum_id FROM learners WHERE id=?', (learner_id,)).fetchone()[0]
            capabilities = book_capabilities(conn, curriculum)
        items = [{**book, 'capabilities': capabilities[book['id']]} if book['id'] in capabilities else book
                 for book in textbook_catalogue(curriculum)]
        return {'items': items, 'subjects': textbook_subjects(curriculum),
                'grade_notice': '二年级英语按学校安排暂未开设。' if curriculum=='math-g2-v1' else
                                '七年级开设以上七门学科；物理从八年级、化学从九年级开始。' if curriculum=='math-g7-v1' else ''}

    @router.post("/api/v1/textbooks/search", response_model=TextbookSearchResponse, response_model_exclude_unset=True)
    def textbook_search(body: dict[str, Any], request: Request, ctx: Context = Depends(get_context),
                        db: Database = Depends(get_db), settings: Settings = Depends(get_settings)):
        def reader(conn, learner, curriculum, directory):
            try:
                scope = textbook_search_scope(curriculum, body)
            except ValueError:
                raise APIError(422, 'TEXTBOOK_SCOPE_INVALID', '请选择当前年级的课本，章节可不选，检索词最多160字')
            if settings.textbook_passages_enabled and scope['mode'] == 'search':
                return textbook_passages.search(settings, curriculum, scope, body['query'])
            return scope
        return read_reference(request, ctx, db, settings, set(), reader)

    @router.get("/api/v1/textbooks/{book_id}/passages/{evidence_id}", response_model=PassageDetail)
    def textbook_passage(book_id: str, evidence_id: str, request: Request, chapter_id: str = '',
                         ctx: Context = Depends(get_context), db: Database = Depends(get_db),
                         settings: Settings = Depends(get_settings)):
        return read_reference(request, ctx, db, settings, {'chapter_id'},
            lambda conn, learner, curriculum, directory:
                textbook_passages.detail(settings, curriculum, book_id, evidence_id, chapter_id))

    @router.get("/api/v1/textbooks/{book_id}/passages/{evidence_id}/image", response_class=Response,
             responses={200: {"content": {"image/png": {}}}})
    def textbook_passage_image(book_id: str, evidence_id: str, request: Request, chapter_id: str = '',
                               ctx: Context = Depends(get_context), db: Database = Depends(get_db),
                               settings: Settings = Depends(get_settings)):
        content = read_reference(request, ctx, db, settings, {'chapter_id'},
            lambda conn, learner, curriculum, directory:
                textbook_passages.detail(settings, curriculum, book_id, evidence_id, chapter_id, image=True))
        return Response(content, media_type='image/png', headers={'X-Content-Type-Options': 'nosniff'})

    @router.get("/api/v1/textbooks/{book_id}/pages/{printed_page}/image", response_class=Response,
             responses={200: {"content": {"image/png": {}}}})
    def textbook_page_image(book_id: str, printed_page: int, request: Request, ctx: Context = Depends(get_context),
                            db: Database = Depends(get_db), settings: Settings = Depends(get_settings)):
        def reader(conn, learner, curriculum, directory):
            try:
                book, pdf_page = textbook_page_scope(curriculum, book_id, printed_page)
            except ValueError:
                raise APIError(404, 'TEXTBOOK_PAGE_NOT_FOUND', '当前年级没有这一教材页')
            try:
                return render_textbook_page(directory, book['id'], pdf_page)
            except (OSError, ValueError, RuntimeError):
                raise APIError(503, 'TEXTBOOK_PAGE_UNAVAILABLE', '教材原页暂时不可用，请稍后重试', True)
        content = read_reference(request, ctx, db, settings, set(), reader)
        return Response(content, media_type='image/png', headers={'X-Content-Type-Options': 'nosniff'})

    return router
