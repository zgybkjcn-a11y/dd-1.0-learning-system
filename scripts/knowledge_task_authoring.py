"""Bounded short answers with authored feedback and explicit knowledge mappings."""
import json
from varied_task_authoring import Tasks,number,choose,table


def N(label,answer,check,unit='',errors=()):
    return number(label,answer,check,unit)|{'kind':'number','errors':list(errors)}


def W(label,answer,*alternatives,case_sensitive=True,errors=()):
    return {'kind':'text','label':label,'answer':answer,'accepted':[answer,*alternatives],
            'case_sensitive':case_sensitive,'units':[],'options':[],'errors':list(errors)}


def C(label,correct,*options):
    return choose(label,correct,*options)|{'kind':'choice'}


def E(answer,message,action):
    return {'answer':str(answer),'message':message,'action':action}


class KnowledgeTasks(Tasks):
    def add_task(self,book,ch,key,page,title,prompt,fields,explanation,*,level='normal',form='短答与检验',task='check',role='direct',visual=None,family=None):
        self.task(book,ch,key,level,form,title,prompt,fields,explanation,page=page,visual=visual,
                  hint='先辨认本题要求的量或词语，再回到条件逐项核对；短答只填本项要求的词语或数值。')
        q=self.questions[-1];q['response_protocol']='short-fields-v2'
        q['knowledge']={'point_id':f'{book}:{ch}:{key}','task':task,'role':role,
                        'family':family or f'{book}:{ch}:{key}:short-reasoning',
                        'rationale':'逐项核对本题明确要求；只计指定结果或辨析，不替代独立口述或实操。'}
        q['design']['family']=q['knowledge']['family'];q['design']['priority']=3
        q['design']['skills']=[title]
