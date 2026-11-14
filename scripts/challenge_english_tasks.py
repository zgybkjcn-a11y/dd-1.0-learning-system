from challenge_task_authoring import N,W,C,M,O,T

def build(b):
 a=b.task;g='english-g7-upper'
 a(g,1,'greeting','先确认名字再回应问候','将对话排成合理顺序：A: Nice to meet you, too. B: Hello! What is your name? C: I am Maya. Nice to meet you. D: My name is Lin. And you?',[
 O('四轮对话顺序','B','D','C','A'),M('从对话可确定',['Maya和Lin交换了姓名','Nice to meet you回应初次见面'],'Maya和Lin交换了姓名','两人住在同一个城市','Nice to meet you回应初次见面','Lin一定比Maya年长')],
 'B先问姓名，D介绍并回问，C回答并问候，A回应问候。未给城市或年龄。',form='对话排序与信息边界')
 a(g,2,'position','移动了什么没有移动什么','Initially: a red bag is on the chair; two keys are in the red bag; a blue box is under the desk. Lin moves the red bag onto the desk without taking anything out. Then she puts one key in the blue box.',[
 W('The red bag ____ on the desk.','is',case_sensitive=False),N('How many keys remain in the red bag?',1,'2-1'),M('最后成立的句子',['One key is in the blue box.','The blue box is under the desk.'],'Both keys are in the bag.','One key is in the blue box.','The red bag is under the chair.','The blue box is under the desk.')],
 '包从椅子到桌上，钥匙随包移动后又拿出一把放蓝盒；盒子位置未变。bag单数用is。',form='连续变化与语法填空')
 a(g,3,'demonstratives','农场里的远近与数量','Near you: 1 horse and 2 ducks. Far from you: 3 cows. Two ducks are taken away, and 1 horse joins the far group of cows. 用this、that、these、those填空。',[
 W('____ is the horse near me.','This',case_sensitive=False),W('____ are the animals far from me.','Those',case_sensitive=False),N('远处现有几只动物',4,'3+1'),M('最终成立',['近处还有1匹马','远处包括牛和马'],'近处还有1匹马','近处还有2只鸭','远处包括牛和马','远处只有3只动物')],
 '近处单数This，远处复数Those；鸭已移走，远处3牛+1马=4。',form='动态数量与指代')
 a(g,4,'personal','两张信息卡和更正通知','Card A: Mia, 13, from China, likes music. Card B: Leo, 12, from Canada, likes drawing. Correction: Leo is 13, not 12; the other details stay the same.',[
 M('按更正后成立',['Mia and Leo are the same age.','Leo likes drawing.'],'Mia and Leo are the same age.','They are from the same country.','Leo likes drawing.','They both like music.'),W('____ Leo from Canada?','Is',case_sensitive=False),N('更正后两人年龄总和',26,'13+13')],
 '只改Leo年龄为13；两人同岁，国籍和爱好各自保留。单数Leo问句用Is。',form='信息更正与句式')
 a(g,5,'relations','关系图和说话人要一起看','Anna and Ben are siblings. Their mother is May. May has a sister, Lily. Lily has a son, Tom. Anna says, “Tom is ____ cousin. Lily is ____ aunt.”',[
 W('Anna说Tom是自己的表亲','my',case_sensitive=False),W('Anna说Lily是自己的姨妈','my',case_sensitive=False),M('关系成立',['Tom is Ben’s cousin.','May is Tom’s aunt.'],'Tom is Ben’s cousin.','May is Tom’s aunt.','Lily is Anna’s mother.','Ben is Tom’s father.')],
 '母亲的姐妹Lily是Anna与Ben的aunt；Lily的儿子Tom是他们的cousin，May也是Tom的aunt。说话人Anna用my。',form='关系网络与物主代词')
 a(g,6,'location','临时改地点后的路线','Route card: The library is between the classroom and the gym. The hall is opposite the gym. Notice: Return books to the hall today; the library is closed. You start at the classroom, pass the library and reach the gym, then cross the road to the hall.',[
 O('按本题路线先后排','classroom','library','gym','hall'),W('____ there a place to return books today?','Is',case_sensitive=False),M('今天成立',['Return books to the hall.','Passing the library does not mean entering it.'],'Return books to the library.','Return books to the hall.','Passing the library does not mean entering it.','The notice says the gym is closed.')],
 '路线经过不等于入内；通知将还书地点改为hall，关闭的是library。问单数a place用Is。',form='路线排序与通知整合')
 a(g,7,'reason','喜欢的程度和原因别混','Mia: Maths is useful, but my favourite is science because I enjoy experiments. Leo: Science is interesting, but I like history best because stories help me understand the past.',[
 W('____ does Mia like science best?','Why',case_sensitive=False),M('材料支持',['Mia最喜欢科学','Leo最喜欢历史','两人给出的理由不同'],'Mia最喜欢科学','Leo最喜欢历史','两人给出的理由不同','useful说明数学是Mia最喜欢的科目'),C('两人都认为科学interesting能否推出最喜欢相同','不能','能','不能')],
 'but区分一般评价和最喜欢，because给理由。Mia选science，Leo选history。',form='偏好层次与理由核对')
 a(g,8,'constraints','社团报名的三项限制','Kai can sing and draw, but cannot swim. He is free only on Tuesday after 4:00. Club A: singing, Tuesday 4:30; B: swimming, Tuesday 4:30; C: drawing, Friday 4:30; D: drawing, Tuesday 5:00. 可同时选时间互不冲突的活动，每次活动20分钟。',[
 M('所有可参加的社团',['A','D'],'A','B','C','D'),W('Kai can ____ (draw).','draw',case_sensitive=False),N('若参加A和D，两次活动间隔几分钟',10,'30-20')],
 'A能力时间都符且4:50结束，D5:00开始；B能力不符，C日期不符。can后动词原形。',form='多条件筛选与日程计算')
 a(g,9,'time','跨中午时间表与动词','Lin leaves home at 11:40 a.m. The bus takes 35 minutes. She waits 10 minutes, then visits a museum for 50 minutes. 完成句子：She ____ (take) the bus every Saturday. Does she ____ (visit) the museum every week?',[
 W('take的形式','takes',case_sensitive=False),W('visit的形式','visit',case_sensitive=False),N('参观结束为下午1点多少分',15,'40+35+10+50-120'),M('时间成立',['12:15 p.m.到达','参观12:25 p.m.开始'],'12:15 a.m.到达','12:15 p.m.到达','参观12:25 p.m.开始','参观12:25 a.m.开始')],
 '到达12:15 p.m.，开始12:25，结束1:15 p.m.。肯定句takes，does后visit。结束时间本题应填1点15分。',form='日程推算与词形')
 a(g,10,'dates','生日当天和聚会不是同一天','Invitation: My birthday is 12 May, but the party is on 14 May, from 3:00 to 5:00 p.m. Come 15 minutes early and bring a cup. The bus takes 20 minutes. Leave at 2:25 p.m. to arrive on time for preparation.',[
 W('12的序数词','twelfth',case_sensitive=False),N('聚会比生日晚几天',2,'14-12'),M('符合邀请的安排',['2:25 p.m.出发坐20分钟公交','带杯子','2:45 p.m.到达准备'],'在12 May参加本次聚会','2:25 p.m.出发坐20分钟公交','带杯子','2:45 p.m.到达准备')],
 '聚会14日，生日12日，相差2天；提前到达2:45，坐20分钟需2:25出发。',form='邀请函综合安排')
 a(g,11,'inference','闭馆通知不能推太远','Notice 1: The library is closed on Monday for repairs. Notice 2: Repairs finish on Tuesday morning; the library opens at 1:00 p.m. on Tuesday. Mia plans to return a book at 10:00 a.m. Tuesday.',[
 M('直接有依据的判断',['周二上午10点尚未开馆','计划需改到周二下午1点或以后'],'周二上午10点尚未开馆','计划需改到周二下午1点或以后','所有图书馆周一都关闭','周二上午修完就立刻开馆'),O('按通知时间排','Monday closure','Tuesday morning repairs finish','Tuesday 1:00 p.m. opens')],
 '完工与开馆是不同时间点，10点仍未到开馆时刻；通知只约束这一图书馆。',form='跨通知推断与排序')
 a(g,12,'script','文字脚本中的两次更正','仅阅读文字脚本，不作真实听力评分。A: Let’s meet at the gym on Wednesday at 4:00. B: The gym is closed. How about the library at 4:30? A: I have class until 4:20 and need 20 minutes to walk there. Can we meet at 4:45? B: OK, Wednesday, library, 4:45.',[
 W('最终地点（一个英语词）','library',case_sensitive=False),N('A下课后到约定时刻共几分钟',25,'45-20'),M('最终成立',['Wednesday见面','A按步行时间4:40能到','最终约在4:45'],'Wednesday见面','A按步行时间4:40能到','最终约在4:45','最终地点是gym')],
 '地点改图书馆，时间由4:00→4:30→4:45；4:20下课走20分钟4:40到，还可提前5分钟。只检查文字理解。',form='脚本更正与时间约束')
 a(g,13,'symbol','先看音标再分组','纸面音标表：ship /ʃɪp/，sheep /ʃiːp/，seat /siːt/，sit /sɪt/。按给定音标比较，不检查实际发音。',[
 M('元音与ship相同的词',['ship','sit'],'ship','sheep','seat','sit'),M('元音与sheep相同的词',['sheep','seat'],'ship','sheep','seat','sit'),C('可以由本题成绩证明的能力','按给定音标辨认两组词','已通过实际听力和发音','按给定音标辨认两组词','所有相近拼写读音必相同')],
 'ship/sit为/ɪ/，sheep/seat为/iː/。两组选择检验纸面辨认，不能计实际听说。',form='交叉分组与证据范围')
 a(g,14,'present','三种句式共享一个事实','Fact: Tom has two cats. His parents have one dog. Fill one word: ____ Tom have two cats? Yes, he ____. His parents do not ____ cats.',[
 W('Tom问句的助动词','Does',case_sensitive=False),W('Tom肯定简答','does',case_sensitive=False),W('do not后的词','have',case_sensitive=False),M('事实支持的句子',['Tom has two cats.','His parents have a dog.'],'Tom has two cats.','His parents have a dog.','Tom have two cats.','Does Tom has two cats?')],
 '第三人称单数用does构成疑问，后接have；简答does。parents为复数，do not后动词原形。',form='句式配对与纠错',page=103)
 a(g,15,'collocation','语境与搭配双重检查','Word bank: library, gym, teacher, hungry, light. Sentence cards: A We read books in the ____. B We play basketball in the ____. C It is dark. Turn on the ____. One word per blank.',[
 W('A','library',case_sensitive=False),W('B','gym',case_sensitive=False),W('C','light',case_sensitive=False),M('合理的检查',['先找活动或状态线索','词库出现不等于每句都能填'],'先找活动或状态线索','词库出现不等于每句都能填','hungry可以表示运动场馆','只按单词长短选择')],
 'read books对应library，basketball对应gym，dark与turn on提示light。联合语义和搭配筛选。',form='语境填空与排除')
 a(g,16,'order','字典排序比到不同字母','词卡：school, scarf, science, score。按英语字母顺序排序，再检验查找策略。',[
 O('字典顺序','scarf','school','science','score'),N('school与science从第几个字母起不同',3,'3'),M('正确的策略',['相同词首后继续向后比','比较第三字母a、h、i、o'],'相同词首后继续向后比','比较第三字母a、h、i、o','只比单词长度','所有sc开头都排同一位置')],
 '四词前两字母sc相同，第三字母a<h<i<o；排scarf、school、science、score。',form='精细排序与规则解释')
 a(g,17,'plural','数量和助动词都要照顾','Correct the forms in a notice: “Two child and three woman have five box. Does one child has a red box?” Fill the plural nouns and choose all grammatically correct corrected questions.',[
 W('child复数','children',case_sensitive=False),W('woman复数','women',case_sensitive=False),W('box复数','boxes',case_sensitive=False),M('语法正确的问句',['Does one child have a red box?','Do the children have boxes?'],'Does one child have a red box?','Do the children have boxes?','Does one child has a red box?','Do the children has boxes?')],
 'children、women为不规则复数，boxes加es；do/does后都用have。',form='短答纠错与语法多选',page=122)
 a(g,18,'numbers','日期中的数词与先后','Event cards: A 3 May; B 21 April; C 12 May; D 2 June. All in the same year. Write the ordinal form of twelve and arrange the events by date.',[
 W('twelve序数词','twelfth',case_sensitive=False),O('按日期从早到晚排','B','A','C','D'),M('成立的说法',['B早于A','D最晚'],'B早于A','D最晚','21 April晚于3 May','12 May比3 May早')],
 '先比月份April、May、June，再比May中3和12；故B、A、C、D。twelve→twelfth。',form='词形与日期排序',page=126)
