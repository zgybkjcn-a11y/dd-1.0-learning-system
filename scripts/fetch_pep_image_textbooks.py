"""Fetch public PEP reader pages; preserve all images and build a local reading PDF."""
import concurrent.futures
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

import fitz
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'learning_data/textbooks/pep-current-20261105'
BOOKS = [('math-g2-lower','1221001202251',106,'数学'),
         ('chinese-g2-lower','1211001202251',130,'语文')]

def fetch(url, target):
    if target.exists() and target.stat().st_size:
        if target.suffix != '.jpg': return
        with Image.open(target) as image: image.verify()
        return
    partial = target.with_suffix(target.suffix + '.partial')
    subprocess.run(['curl','-fsSL','--retry','2','--max-time','90',
                    '-e','https://jc.pep.com.cn/','-A','Mozilla/5.0',url,'-o',str(partial)],check=True)
    if target.suffix == '.jpg':
        with Image.open(partial) as image: image.verify()
    partial.replace(target)

def main():
    for key, book_id, count, subject in BOOKS:
        directory = DEST / f'{key}-reading-images'
        directory.mkdir(parents=True,exist_ok=True)
        source = f'https://book.pep.com.cn/{book_id}/'
        # Independent public reading source; official reader requires a human slider.
        slug = 'sxr22' if subject == '数学' else 'yw22'
        image_base = 'shuxue/rjb' if subject == '数学' else 'yuwen/bbb'
        reading_source = f'https://www.keben1.com/a/{slug}/keben.html'
        fetch(reading_source,directory/'source.html')
        assert int(re.search(r'totalpage\s*=\s*(\d+)',(directory/'source.html').read_text())[1]) == count
        def one(number):
            p = directory / f'{number:03d}.jpg'
            # The public site stores front matter as 000mN and body as NNN.
            front = 5
            filename = f'000m{number}.jpg' if number<=front else f'{number-front:03d}.jpg'
            url=f'https://www.keben1.com/uploads/book/{image_base}/22/{filename}'
            fetch(url,p)
            time.sleep(0.4)
            return {'page':number,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'url':url}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            pages = list(pool.map(one,range(1,count+1)))
        pdf = DEST / f'{key}.pdf'
        with fitz.open() as document:
            for n in range(1,count+1):
                data=(directory/f'{n:03d}.jpg').read_bytes()
                with fitz.open(stream=data,filetype='jpeg') as img:
                    rect=img[0].rect
                document.new_page(width=rect.width,height=rect.height).insert_image(rect,stream=data)
            document.set_metadata({'title':f'义务教育教科书 {subject} 二年级下册（人教社现行新版）',
                                   'subject':'Local reading copy of public official reader images; no OCR text yet',
                                   'author':'人民教育出版社'})
            document.save(pdf,deflate=True)
        record={'key':key,'source_url':reading_source,'official_reader':source,'official_catalog':'https://jc.pep.com.cn/',
                'source_metadata':{'grade':'二年级','subject':subject,'semester':'下册','system':'六三制',
                                   'publishers':['人民教育出版社'],'version':'统编版' if subject=='语文' else '人教版',
                                   'revision':None,'revision_basis':'2022课标新修订系列；2026春官方在用电子版，版权页未填版次'},
                'pages':count,'bytes':pdf.stat().st_size,'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),
                'pdf':str(pdf.relative_to(ROOT)),'page_sources':pages,'extraction':'images-awaiting-authorized-offline-ocr'}
        (DEST/f'{key}-manifest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
        print(json.dumps({'key':key,'pages':count,'downloaded':True}),flush=True)

if __name__=='__main__': main()
