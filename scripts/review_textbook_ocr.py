"""Offline OCR staging and item quality report; never imports or approves pages.

The two authorized public Grade 2 books only. Downloaded image verification,
OCR confidence, visual review, and mathematical review remain separate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from learning_service.textbook_quality import assess_item


def main(image_dir, output, library_dir):
    image_dir=image_dir.resolve()
    output=output.resolve()
    assert image_dir.name in {'math-g2-lower-images','math-g2-lower-reading-images',
                              'chinese-g2-lower-images','chinese-g2-lower-reading-images',
                              'math-g2-lower-public-preview','chinese-g2-lower-public-preview'}
    sys.path.insert(0,str(library_dir))
    import onnxruntime
    onnxruntime.disable_telemetry_events()
    from rapidocr_onnxruntime import RapidOCR
    from PIL import Image
    ocr=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=2)
    output.mkdir(parents=True,exist_ok=True)
    results=[]
    for path in sorted(image_dir.glob('*.jpg')):
        try:
            with Image.open(path) as image: image.verify()
        except Exception:
            results.append({'page':path.stem,'status':'rejected_not_an_image'})
            continue
        sha=hashlib.sha256(path.read_bytes()).hexdigest()
        destination=output/(path.stem+'.json')
        if destination.exists():
            prior=json.loads(destination.read_text())
            if prior['image_sha256']==sha: results.append(prior);continue
        recognized,_=ocr(str(path));lines=[]
        for box,text,confidence in recognized or []:
            # No human/source review supplied here: even correct arithmetic is
            # quarantined until faithful, complete transcription is verified.
            lines.append({'box':box,'text':text,'confidence':confidence,
                          'quality':assess_item(text,sha,{})})
        result={'page':path.stem,'source_image':str(path.relative_to(ROOT)),
                'image_sha256':sha,'engine':'RapidOCR 1.4.4 / local PP-OCRv4 ONNX',
                'status':'quarantined_pending_visual_and_semantic_review',
                'low_confidence_lines':sum(x['confidence']<.97 for x in lines),
                'lines':lines,'eligible_for_question_or_answer':False}
        destination.write_text(json.dumps(result,ensure_ascii=False,indent=2))
        results.append(result)
        print(json.dumps({'page':path.stem,'lines':len(lines),'low_confidence_lines':result['low_confidence_lines'],'approved':False}),flush=True)
    report={'engine_calls_external':0,'images_seen':len(results),
            'valid_images':sum('image_sha256' in r for r in results),
            'fully_verified_pages':0,'question_or_answer_eligible_pages':0,
            'pages':[{'page':r['page'],'status':r['status']} for r in results]}
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('image_dir',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--library-dir',type=Path,default=Path('/tmp/dd-textbook-ocr-libs'));a=p.parse_args()
    main(a.image_dir,a.output,a.library_dir)
