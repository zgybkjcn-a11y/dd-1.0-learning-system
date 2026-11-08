"""Root-level test options, portable inputs and pre-import isolation."""
import hashlib
import importlib
import ipaddress
import json
import os
from pathlib import Path
import shutil
import socket
import tempfile

import pytest


def pytest_addoption(parser):
    group = parser.getgroup("dd-tests")
    group.addoption("--browser-executable", default=os.getenv("DD_BROWSER_EXECUTABLE"),
                    help="Chromium executable; default is the pinned Playwright browser")
    group.addoption("--browser-version", default=os.getenv("DD_BROWSER_VERSION"),
                    help="Require this exact browser.version when using a custom executable")
    group.addoption("--textbook-dir", help="Explicit directory for -m local_materials only")
    group.addoption("--fail-on-skip", action="store_true", help="Fail if any selected test skips")


def pytest_configure(config):
    # app.py creates its default app at import time. Isolate BEFORE collection,
    # including subprocesses, and remove inherited provider/secret-file settings.
    patch = pytest.MonkeyPatch()
    scratch = tempfile.TemporaryDirectory(prefix="dd-pytest-bootstrap-")
    config.add_cleanup(scratch.cleanup)
    config.add_cleanup(patch.undo)
    for name in tuple(os.environ):
        if name.startswith(("LEARNING_", "TENCENT_OCR_", "DD_GATEWAY_", "DD_FAMILY_SETUP_")):
            patch.delenv(name)
    patch.setenv("LEARNING_DATA_DIR", scratch.name)
    patch.setenv("LEARNING_TEXTBOOK_DIR", str(Path(scratch.name) / "no-real-textbooks"))
    patch.setenv("LEARNING_MODEL_EXTERNAL_CALLS_ENABLED", "0")
    patch.setenv("TENCENT_OCR_EXTERNAL_CALLS_ENABLED", "0")
    config._dd_skips = []
    config._dd_browser_versions = set()

    # No external Python sockets, including during test collection. ASGI clients
    # need none; the transport tests use disposable loopback HTTP servers.
    original_connect, original_connect_ex = socket.socket.connect, socket.socket.connect_ex
    original_lookup = socket.getaddrinfo

    def require_loopback(host):
        if host in (None, "localhost", b"localhost"):
            return
        try:
            if ipaddress.ip_address(host).is_loopback:
                return
        except ValueError:
            pass
        raise RuntimeError("Test network isolation: non-loopback connection blocked")

    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            require_loopback(address[0])
        return original_connect(sock, address)

    def connect_ex(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            require_loopback(address[0])
        return original_connect_ex(sock, address)

    def lookup(host, *args, **kwargs):
        require_loopback(host)
        return original_lookup(host, *args, **kwargs)

    patch.setattr(socket.socket, "connect", connect)
    patch.setattr(socket.socket, "connect_ex", connect_ex)
    patch.setattr(socket, "getaddrinfo", lookup)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    report = (yield).get_result()
    if report.skipped:
        item.config._dd_skips.append(item.nodeid)


def pytest_sessionfinish(session, exitstatus):
    if session.config.getoption("--fail-on-skip") and session.config._dd_skips and exitstatus == 0:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter, config):
    if config._dd_browser_versions:
        terminalreporter.write_line("DD Chromium versions: " + ", ".join(sorted(config._dd_browser_versions)))
    if config.getoption("--fail-on-skip") and config._dd_skips:
        terminalreporter.write_line("DD required tests skipped (failure): " + ", ".join(config._dd_skips), red=True)


@pytest.fixture(scope="session")
def playwright():
    try:
        return importlib.import_module("playwright.sync_api")
    except ImportError:
        pytest.fail("Browser tests require requirements-dev.lock and python -m playwright install chromium", pytrace=False)


@pytest.fixture
def launch_browser(pytestconfig):
    def launch(runtime):
        options = {"headless": True}
        executable = pytestconfig.getoption("--browser-executable")
        expected = pytestconfig.getoption("--browser-version")
        if executable:
            options["executable_path"] = executable
        else:
            # Use Playwright's pinned full Chromium in its current headless mode;
            # this needs no separate headless-shell download or system Chrome.
            options["channel"] = "chromium"
        browser = runtime.chromium.launch(**options)
        pytestconfig._dd_browser_versions.add(browser.version)
        if expected and browser.version != expected:
            actual = browser.version
            browser.close()
            pytest.fail(f"Chromium version mismatch: expected {expected}, got {actual}")
        return browser
    return launch


@pytest.fixture(scope="session")
def synthetic_pdf_set(tmp_path_factory):
    import fitz
    from learning_service.textbooks import BOOKS

    directory = tmp_path_factory.mktemp("synthetic-pdf-masters")
    for book in BOOKS:
        offset = book['chapters'][0]['page_start'] - book['chapters'][0]['printed_page']
        with fitz.open() as doc:
            for n in range(1, book['chapters'][-1]['page_end'] + 1):
                page = doc.new_page(width=320, height=440)
                page.insert_text((30, 40), f"SYNTHETIC {book['id']} - page {n-offset}")
                page.insert_text((40, 100), 'n * x = l / 2', fontsize=18)
                page.draw_line((60, 200), (240, 200))
                page.draw_rect((100, 230, 115, 250), fill=(0.2, 0.5, 0.7))
                page.draw_line((150, 200), (150, 160))
                page.insert_text((30, 410), str(n-offset))
            (directory / (book['id'] + '.pdf')).write_bytes(doc.tobytes(deflate=True, no_new_id=True))
    return directory


@pytest.fixture
def textbook_sources(tmp_path, monkeypatch, synthetic_pdf_set):
    from learning_service.textbooks import PDF_SHA256

    directory = tmp_path / 'textbooks'
    shutil.copytree(synthetic_pdf_set, directory)
    for path in directory.glob('*.pdf'):
        monkeypatch.setitem(PDF_SHA256, path.stem, hashlib.sha256(path.read_bytes()).hexdigest())
    return directory


@pytest.fixture
def reference_textbooks(textbook_sources, tmp_path, monkeypatch):
    from learning_service import math_references as references
    from learning_service.textbooks import PDF_SHA256

    # Keep the real validation path: bind a temporary reference JSON to the
    # synthetic PDFs, rather than replacing the hash checker or query function.
    original = json.loads(references.REFERENCE_PATH.read_text())
    replacements = {old: PDF_SHA256[book] for book, old in original['pdf_sha256'].items()}

    def rebind(value):
        if isinstance(value, dict):
            return {k: rebind(v) for k, v in value.items()}
        if isinstance(value, list):
            return [rebind(v) for v in value]
        return replacements.get(value, value) if isinstance(value, str) else value

    path = tmp_path / 'synthetic-references.json'
    path.write_text(json.dumps(rebind(original), ensure_ascii=False))
    monkeypatch.setattr(references, 'REFERENCE_PATH', path)
    monkeypatch.setattr(references, 'REFERENCE_SHA256', hashlib.sha256(path.read_bytes()).hexdigest())
    return textbook_sources
