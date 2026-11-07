import pytest

from learning_service.textbook_quality import assess_item, check_arithmetic_claim, check_remainder, content_hash


def proof(text):
    return {'status':'verified','content_sha256':content_hash(text),'image_sha256':'a'*64,
            'scope':'complete_item','layout_checked':True,
            'evidence':'synthetic visual comparison'}


def test_faithful_ocr_of_wrong_original_is_rejected():
    text = '8 ÷ 2 = 5'
    result = assess_item(text,'a'*64,proof(text))
    assert result['transcription_status'] == 'verified'
    assert result['mathematical_review']['status'] == 'rejected'
    assert not result['eligible_for_question_or_answer']


def test_correct_arithmetic_without_transcription_review_is_not_approved():
    result = assess_item('8 ÷ 2 = 4','a'*64,{'confidence':1.0})
    assert result['mathematical_review']['status'] == 'verified'
    assert result['status'] == 'quarantined'


@pytest.mark.parametrize('text', ['3 − (−2) = 5','1/3 + 1/6 = 1/2','7 × 8 = 56'])
def test_independent_exact_calculation(text):
    assert assess_item(text,'a'*64,proof(text))['eligible_for_question_or_answer']


@pytest.mark.parametrize('text', ['6 ÷ 0 = 0','3 + □ = 5','图中有多少个？','3米+2厘米=5米',
                                '__import__("os").system("false")=0','2**1000000000=0'])
def test_unsupported_or_incomplete_claims_require_review(text):
    assert check_arithmetic_claim(text)['status'] == 'needs_review'
    assert not assess_item(text,'a'*64,proof(text))['eligible_for_question_or_answer']


def test_editing_text_or_source_invalidates_previous_review():
    old='3+2=5'
    assert not assess_item('3+3=6','a'*64,proof(old))['eligible_for_question_or_answer']
    assert not assess_item(old,'b'*64,proof(old))['eligible_for_question_or_answer']


def test_generic_review_flag_cannot_approve_word_problem():
    text='小明有3米绳子，用去20厘米，还剩多少厘米？'
    assert not assess_item(text,'a'*64,proof(text),{'status':'verified'})['eligible_for_question_or_answer']


@pytest.mark.parametrize('text', ['1 2 = 12', '1\n2=12', '3\n+2=5'])
def test_layout_cannot_be_removed_to_manufacture_a_correct_equation(text):
    assert check_arithmetic_claim(text)['status'] == 'needs_review'


def test_crop_cannot_approve_a_complete_item():
    text = '13=4×3+1'
    review = {**proof(text), 'scope':'ocr_line'}
    assert not assess_item(text,'a'*64,review)['eligible_for_question_or_answer']


@pytest.mark.parametrize('values,valid', [((13,4,3,1),True), ((12,4,3,0),True),
    ((13,4,2,5),False), ((13,4,4,-3),False), ((13,0,3,13),False), ((13,4,3,2),False)])
def test_remainder_checks_range_as_well_as_reconstruction(values, valid):
    assert (check_remainder(*values)['status'] == 'verified') is valid


def test_editing_answer_invalidates_independent_review():
    text = '11盒酸奶，每4盒装一袋，装几袋，还剩几盒？'
    answer = '2袋，余3盒'
    review = {'status':'verified','method':'independent_review','content_sha256':content_hash(text),
              'image_sha256':'a'*64,'answer_sha256':content_hash(answer),'conditions_complete':True,
              'units_checked':True,'diagram_checked':True,'derivation':'11=4×2+3, 0≤3<4',
              'evidence':'synthetic independent review'}
    assert assess_item(text,'a'*64,proof(text),review,answer=answer)['eligible_for_question_or_answer']
    assert not assess_item(text,'a'*64,proof(text),review,answer='3袋，余1盒')['eligible_for_question_or_answer']
