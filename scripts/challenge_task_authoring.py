"""Original bounded tasks with mixed response modes and editorial challenge demand."""
import hashlib,json
from chapter_practice_authoring import Batch
from knowledge_task_authoring import N,W,C,E
from varied_task_authoring import table as T
from learning_service.textbooks import learning_scope


def M(label, correct, *options):
    assert correct and set(correct)<set(options) and len(set(options))==len(options)
    return dict(kind='multi',label=label,answer=','.join(str(options.index(x)+1) for x in correct),units=[],options=list(options))


def O(label, *ordered):
    assert len(set(ordered))==len(ordered)
    return dict(kind='order',label=label,answer=','.join(str(i+1) for i in range(len(ordered))),units=[],options=list(ordered))


class ChallengeTasks(Batch):
    def task(self,book,ch,point,title,prompt,fields,explanation,*,level='challenge',form='条件推理与多选',page=None,demand='同时整合多个条件，检验候选并排除越界结论',task=None):
        ch=str(ch);grade=int(book.split('-g')[1][0])
        self.add(book,ch,level,title,prompt+'\n完成所有作答项；多选需选全且不多选，排序按题目指定顺序。',0,'0','把条件列清，逐个检查候选；排序前先确定比较标准。',explanation)
        q=self.questions[-1];q['id']=f'family-chapter-{book}-{ch}-challenge_variety-{len(self.questions):03}-v1'
        for i,f in enumerate(fields):
            f['id']=chr(97+i)
            if f['options']:
                indices=f['answer'].split(',');correct=[f['options'][int(n)-1] for n in indices]
                shift=hashlib.sha256((q['id']+f['id']).encode()).digest()[0]%len(f['options'])
                if f['kind']=='order':shift=1+shift%(len(f['options'])-1)
                f['options']=f['options'][shift:]+f['options'][:shift]
                f['answer']=','.join(str(f['options'].index(v)+1) for v in correct)
                if f['kind']=='choice':f['independent_check']=f['answer']
        q['response_protocol']='structured-fields-v3';q['responses']=fields
        q['answer']=json.dumps({f['id']:f['answer'] for f in fields},ensure_ascii=False,separators=(',',':'));del q['independent_check']
        _,c=learning_scope(f'math-g{grade}-v1',book,ch)
        q['source'].update(topic_printed_pages=[page or c['printed_page']],reference_scope='topic_location_not_verbatim_question',basis='固定教材主题位置；题干、材料和图表为项目自编')
        q['extension']=level in ('hard','challenge')
        q['design']=dict(form=form,family=f'{book}:{ch}:{title}',priority=4,order=len(self.questions),skills=[point],demand=demand,assessment_limit='只核对明确结果与选择；不等于开放表达、听说或实操达标。')
        q['knowledge']=dict(point_id=f'{book}:{ch}:{point}',task=task or ('transfer' if book in ('math-g2-upper','math-g7-upper') else 'check'),role='supporting',family=q['design']['family'],rationale='综合任务只涉及本项部分要求，保守计辅助；不替代独立表达、操作或完整要求。')
