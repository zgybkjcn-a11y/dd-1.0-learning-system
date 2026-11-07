ARG RUNTIME_BASE=python@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30
FROM ${RUNTIME_BASE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    LEARNING_DATA_DIR=/var/lib/dd-learning \
    LEARNING_DB_PATH=/var/lib/dd-learning/learning.db \
    LEARNING_ATTACHMENT_DIR=/var/lib/dd-learning/attachments \
    LEARNING_EXPORT_DIR=/var/lib/dd-learning/exports \
    LEARNING_DOCUMENT_PROVIDER=mock-document-v1 \
    LEARNING_DIAGNOSIS_PROVIDER=mock-diagnosis-v1 \
    LEARNING_VARIANT_PROVIDER=mock-variant-v1

WORKDIR /app
COPY deploy/open-webui-reuse/requirements.lock /app/requirements.lock
COPY dependency-wheels /app/dependency-wheels
RUN pip install --no-cache-dir --no-index --find-links=/app/dependency-wheels --require-hashes -r /app/requirements.lock \
    && rm -rf /app/dependency-wheels
COPY learning_service /app/learning_service

RUN useradd --create-home --uid 10001 learning \
    && mkdir -p /var/lib/dd-learning/attachments /var/lib/dd-learning/exports \
    && chown -R learning:learning /var/lib/dd-learning
USER learning

EXPOSE 31010
CMD ["python", "-m", "learning_service.app"]
