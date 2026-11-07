"""Recheck the recorded, directly inspected public-page samples offline.

The visual judgments below are Codex assistant review, not a human sign-off.
This report neither approves a whole page/book nor publishes any question.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from learning_service.textbook_quality import assess_item, check_arithmetic_claim, check_remainder, content_hash

EVIDENCE = ROOT / 'learning_data/verification/family-textbooks-20261105'
IMAGES = ROOT / 'learning_data/textbooks/pep-current-20261105'


def main():
    reviewer = 'Codex assistant: direct image inspection and independent calculation; not human sign-off'
    examples = [
        (16, 'example-1',
         '用9根小棒摆互不共边的正方形，每个用4根。摆2个，还剩1根。9÷4=2（个）……1（根）。',
         None, (9,4,2,1),
         '图中9根小棒分别组成两个四边形，另余1根；商的单位为个，余数单位为根。',
         '4×2+1=9，且0≤1<4。图形彼此独立、没有共用边；9÷4的余数记法不能误读为普通等式9/4=2+1。'),
        (20, 'worked-reconstruction', '13=4×3+1', None, None,
         '第14页上部横式，与上方竖式商3、除数4、被除数13、积12、余数1对应。',
         '单独验算乘加：4×3=12，12+1=13；有余数除法另验0≤1<4。'),
        (20, 'exercise-1-1',
         '用小棒表示酸奶，摆一摆，填一填，并写出竖式。（1）11盒酸奶，每4盒装一袋。装了□袋，还剩□盒。11÷4=□（袋）……□（盒）。',
         '装2袋，还剩3盒。竖式：商2，除数4，被除数11，乘积8，余数3。', (11,4,2,3),
         '第14页做一做第1（1）题；小棒是酸奶的表示符号，题干已给11盒及每袋4盒，无须从缺失图形猜总量。',
         '每袋4盒，2袋用8盒；11−8=3盒，0≤3<4，不能再装满一袋。商单位为袋、余数为盒。'),
    ]
    reviews = []
    for page, key, text, answer, division, visual, derivation in examples:
        image = IMAGES / 'math-g2-lower-images' / f'{page:03}.jpg'
        image_hash = hashlib.sha256(image.read_bytes()).hexdigest()
        ocr = EVIDENCE / 'ocr-math-g2-lower' / f'{page:03}.json'
        raw = json.loads(ocr.read_text())
        assert raw['image_sha256'] == image_hash
        arithmetic = check_remainder(*division) if division else check_arithmetic_claim(text)
        assert arithmetic['status'] == 'verified'
        if not division:
            assert check_remainder(13,4,3,1)['status'] == 'verified'
        transcription = {'status':'verified','scope':'complete_item','layout_checked':True,
                         'image_sha256':image_hash,'content_sha256':content_hash(text),
                         'evidence':visual,'reviewer':reviewer}
        semantic = {'status':'verified','method':'independent_review','content_sha256':content_hash(text),
                    'image_sha256':image_hash,'answer_sha256':content_hash(answer or ''),
                    'conditions_complete':True,'units_checked':True,'diagram_checked':True,
                    'derivation':derivation,'evidence':arithmetic,'reviewer':reviewer}
        result = assess_item(text,image_hash,transcription,semantic,answer=answer)
        assert result['eligible_for_question_or_answer']
        reviews.append({'id':key,'source_image':str(image.relative_to(ROOT)),
                        'source_url':f'https://book.pep.com.cn/1221001202251/files/mobile/{page}.jpg',
                        'reader_image_number':page,'printed_page':page-6,
                        'raw_ocr_sha256':hashlib.sha256(ocr.read_bytes()).hexdigest(),
                        'reviewed_text':text, 'text_kind':'reviewed_transcription_with_explicit_diagram_description',
                        'derived_review_answer':answer,'answer_is_from_textbook':False if answer else None,
                        'transcription_review':transcription,'content_review':semantic,'quality':result,
                        'published_to_question_bank':False})
    defects = []
    for subject,page,old,correct,issue in [
        ('math',14,'圭表和日被称为','圭表和日晷被称为','漏字：晷；原图可见，不按OCR残句生成知识点。'),
        ('chinese',6,'苗助长','揠苗助长','课文标题漏首字；不能把三字残句当成成语。'),
        ('math',20,'除数413','除数4，被除数13；商3、积12、余数1','竖式空间关系被丢失；不是413，也不是4/13。'),
    ]:
        image = IMAGES / f'{subject}-g2-lower-images' / f'{page:03}.jpg'
        ocr = EVIDENCE / f'ocr-{subject}-g2-lower' / f'{page:03}.json'
        raw = json.loads(ocr.read_text())
        assert any(old in line['text'] for line in raw['lines'])
        defects.append({'subject':subject,'image_number':page,'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),
                        'ocr_fragment':old,'visually_checked_correction':correct,'issue':issue,
                        'raw_text_preserved':True,'whole_page_approved':False,
                        'independent_fact_check':'pending' if subject=='chinese' or page==14 else 'see worked-reconstruction'})
    report = {'scope':'selected items only; neither full-page nor full-book approval',
              'reviewer':reviewer,'external_model_calls':0,'new_ocr_calls':0,
              'fully_verified_pages':0,'questions_published':0,'items':reviews,'defects':defects}
    (EVIDENCE/'sample-content-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'reviewed_items':len(reviews),'documented_defects':len(defects),
                      'fully_verified_pages':0,'questions_published':0}))


if __name__ == '__main__':
    main()
