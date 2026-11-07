"""Download the explicitly selected public textbook editions; retain source metadata."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import threading

import fitz
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'learning_data/textbooks/pep-current-20261105'
BOOKS = {'0015':'math-g2-upper', '0027':'chinese-g2-upper',
         '0079':'math-g7-upper', '0080':'math-g7-lower',
         '0073':'chinese-g7-upper', '0074':'chinese-g7-lower',
         '0177':'english-g7-upper', '0179':'geography-g7-upper',
         '0189':'biology-g7-upper', '0194':'history-g7-upper',
         '0085':'ethics-g7-upper'}
PDF_LOCK = threading.Lock()

def unpack(value):
    if isinstance(value, list) and len(value) == 2 and value[0] in (0, 1):
        return unpack(value[1])
    if isinstance(value, dict):
        return {k: unpack(v) for k, v in value.items()}
    if isinstance(value, list):
        return [unpack(v) for v in value]
    return value

def fetch(url, target):
    if target.exists() and target.stat().st_size:
        return
    partial = target.with_suffix(target.suffix + '.partial')
    subprocess.run(['curl','-fL','--retry','2','--max-time','600','-C','-',url,'-o',str(partial)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    partial.replace(target)

def book(item):
    identifier, key = item
    source = f'https://keben.app/book/{identifier}'
    fetch(source, DEST / f'{key}.html')
    soup = BeautifulSoup((DEST / f'{key}.html').read_text(), 'html.parser')
    metadata = next(unpack(json.loads(i['props']))['book'] for i in soup.select('astro-island[props]')
                    if '"book"' in i['props'])
    assert metadata['system'] == '六三制'
    assert '人民教育出版社' in metadata['publishers']
    assert metadata['revision'] == 2024
    fetch(f'https://keben.app/api/download/{identifier}', DEST / f'{key}-download.json')
    download = json.loads((DEST / f'{key}-download.json').read_text())
    url = download.get('downloadUrl') or download['primaryUrl']
    assert url.startswith('https://media.keben.app/')
    pdf = DEST / f'{key}.pdf'
    # Reuse the already verified math downloads.
    previous = ROOT / 'learning_data/textbooks/pep-2024-grade7' / pdf.name
    if not pdf.exists() and previous.exists():
        import shutil
        shutil.copyfile(previous, pdf)
    fetch(url, pdf)
    with PDF_LOCK:
        with fitz.open(pdf) as document:
            pages = [p.get_text() for p in document]
    text = '\n'.join(pages)
    (DEST / f'{key}.txt').write_text(text)
    (DEST / f'{key}-pages.json').write_text(json.dumps(pages, ensure_ascii=False))
    record = {'key':key,'source_url':source,'pdf_url':url,'source_metadata':metadata,
              'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'bytes':pdf.stat().st_size,
              'pages':len(pages),'characters':len(text),'blank_text_pages':sum(len(p.strip())<10 for p in pages),
              'pdf':str(pdf.relative_to(ROOT)), 'extraction':'pymupdf-local-no-ocr'}
    (DEST / f'{key}-manifest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
    print(json.dumps({k:record[k] for k in ['key','pages','characters','blank_text_pages']},ensure_ascii=False),flush=True)
    return record

if __name__ == '__main__':
    DEST.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(book, BOOKS.items()))
    (DEST / 'download-manifest.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
