"""Author the sixth lower-book candidate batch, without registering it.

Batch 6 covers 七下英语 Unit 5—8 and Reading Plus plus 二下数学 activity1 (two
inventoried points). Batches 1—5 stay byte-identical in their own files and
evidence packages. Only writes a new local JSON on explicit invocation; no
app/DB/provider imports.
"""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from knowledge_task_authoring import KnowledgeTasks, C, N, E

ROOT = Path(__file__).resolve().parents[1]
BATCH = "lower_gap_candidates_batch6"
DESTINATION = ROOT / "learning_service/data/family_chapter_lower_gap_candidates_batch6_v1.json"
DEFAULT_SOURCE_LIMIT = "固定原页只作主题与学科事实依据；题目、情境与数据均为本地自编。"


def build():
    batch = KnowledgeTasks(BATCH)

    def add(point, key, pages, title, prompt, fields, explanation, *, actions,
            difficulty, review, misconceptions=(), role="direct", manual=None,
            visual=None, source_limit=DEFAULT_SOURCE_LIMIT):
        book, chapter, _ = point.split(":")
        batch.add_task(book, chapter, key, pages[0], title, prompt, fields,
                       explanation, family=f"{point}:{key}", role=role, visual=visual,
                       level="normal", form=title)
        q = batch.questions[-1]
        q["knowledge"].update(point_id=point, rationale=review)
        q["source"].update(topic_printed_pages=pages, evidence_limit=source_limit)
        q["design"].update(core_actions=actions, difficulty_rationale=difficulty)
        q["review"].update(status="assistant_checked", content_check=review,
                           curriculum_standard_crosscheck="pending",
                           deployment_status="local_candidate_not_registered")
        q["review"]["field_coverage"] = {
            f["id"]: action for f, action in zip(q["responses"], actions, strict=True)}
        messages = []
        for field, items in zip(q["responses"], misconceptions, strict=True):
            errors = []
            for text, message, action in items:
                if field["kind"] == "choice":
                    index = field["options"].index(text) + 1
                    assert str(index) != field["answer"], (point, text)
                    errors.append(E(str(index), message, action))
                elif field["kind"] == "number":
                    assert text != field["answer"], (point, text)
                    errors.append(E(text, message, action))
                else:
                    raise AssertionError("batch 6 authors only choice and number fields")
                messages.append(message)
            field["errors"] = errors
        q["common_error_feedback"] = (
            "常见错误：" + "；".join(m.rstrip("。. ") for m in messages)
            + "。逐项回到题干给出的条件核对后再作答。"
            if messages else "按题干给出的条件逐项核对，不要只凭印象作答。")
        if manual:
            q["manual_followup"] = {
                "prompt": manual[0], "criteria": manual[1],
                "automatically_graded": False, "completion": "not_observed",
                "reviewer": None, "learner_record_created": False,
                "example_is_not_unique_answer": True}

    # ------------------------------- 二下数学 时间在哪里·钟面（p2/3，图像核对）
    add("math-g2-lower:activity1:inventory-1", "clock-face", [2, 3],
        "钟面上的大格、小格与时间单位",
        "下面是本题自编的钟面问题，按二年级“时间在哪里”的读数与单位关系作答。",
        [N("钟面上一共有多少个大格？", 12, "12", "个"),
         N("钟面上一共有多少个小格？", 60, "60", "个"),
         N("1 时 20 分一共是多少分？", 80, "1*60+20", "分"),
         C("小明 8 时开始写作业，8 时 30 分写完。“写作业用了 30 分”中的 30 分表示什么？",
           "经过的时间", "开始的时刻", "结束的时刻", "钟面上的大格数", "经过的时间")],
        "钟面上有 12 个大格，每个大格分成 5 个小格，一共有 12×5=60 个小格。"
        "时针转 1 大格是 1 时，分针转 1 小格是 1 分，秒针转 1 小格是 1 秒；"
        "1 时=60 分，1 分=60 秒，所以 1 时 20 分是 60+20=80 分。"
        "“8 时”是开始的时刻，“30 分”是从开始到结束经过的时间，时刻和经过时间要分开说。",
        actions=["数出钟面的大格数", "由大格与小格关系算出小格总数",
                 "用 1 时=60 分换算复名数", "区分时刻与经过时间"],
        difficulty="前三项要求把钟面结构与单位关系连起来，第三项还要先换时再合分；"
                   "第四项要求在同一句话里把“8 时”和“30 分”分别归为时刻与经过时间。",
        review="12、60、80 均独立复算；钟面 12 大格、每大格 5 小格、1 时=60 分、"
               "1 分=60 秒与“时针转 1 大格是 1 时”在第 2、3 页原页图像中逐项核对。",
        misconceptions=[
            [("24", "钟面上是 12 个大格，24 是一天的小时数。", "数一数钟面上的数字个数。"),
             ("60", "60 是小格总数，不是大格数。", "区分大格与小格。")],
            [("12", "12 是大格数，每个大格还有 5 个小格。", "用 12×5 算小格总数。"),
             ("5", "5 是每个大格里的小格数。", "看“钟面上一共”。")],
            [("60", "只换了 1 时，忘了加上 20 分。", "先算 1 时=60 分，再加 20 分。"),
             ("120", "把 20 分当成了 60 分。", "分与分直接相加。")],
            [("开始的时刻", "“8 时”才是开始的时刻。", "区分句中的两个时间。"),
             ("结束的时刻", "结束的时刻是 8 时 30 分。", "看 30 分说的是长度还是位置。"),
             ("钟面上的大格数", "30 分与钟面大格数没有直接关系。", "回到“用了”这个词。")]],
        manual=("实际拨钟、测量 1 分钟活动并记录；说明自己记录的是时刻还是时长。",
                ["说明具体材料或步骤", "理由与本条知识相符",
                 "保留实际表现及所用提示，不以模板代替"]),
        source_limit="第 2、3 页原页图像支持钟面 12 大格、每大格 5 小格、60 小格、"
                     "1 时=60 分、1 分=60 秒与时刻读法；本册无原生文字层，未使用 OCR。")

    # ------------------------------- 二下数学 时间小书（p5/7，图像核对）
    add("math-g2-lower:activity1:inventory-2", "schedule-durations", [5, 7],
        "作息记录中的起止时刻与经过时间",
        "下面是本题自编的作息记录：第一节课 8:20—9:00；体育锻炼 9:10—9:45；"
        "阅读 10:00—10:30。都发生在同一天上午，按记录作答。",
        [N("第一节课从 8:20 到 9:00，经过了多少分？", 40, "9*60-(8*60+20)", "分"),
         N("体育锻炼从 9:10 到 9:45，经过了多少分？", 35, "9*60+45-(9*60+10)", "分"),
         N("阅读从 10:00 到 10:30，经过了多少分？", 30, "10*60+30-10*60", "分"),
         C("下面哪一项记录的是经过的时间，而不是时刻？",
           "40 分", "8:20", "9:00", "9:45", "40 分")],
        "作息记录里的 8:20、9:00、9:10、9:45、10:00、10:30 都是时刻；两项时刻之间的"
        "差才是经过的时间。8:20 到 9:00 相差 40 分；9:10 到 9:45 相差 35 分；10:00 到 "
        "10:30 相差 30 分。时刻表示“什么时候”，经过时间表示“用了多久”，两者不能混说。",
        actions=["由起止时刻求第一段经过时间", "求第二段经过时间",
                 "求第三段经过时间", "区分经过时间与时刻的记录"],
        difficulty="三项都要求从成对的时刻求差，且分钟数不为整时，需要先算到整时再补分钟；"
                   "第四项要求在一个数值和三个时刻中判断哪一个是时长。",
        review="40、35、30 均独立复算（9:00−8:20=40 分，9:45−9:10=35 分，"
               "10:30−10:00=30 分）；作息表式样与“需要时间／时刻”两种记录对应第 5 页，"
               "1 时=60 分的关系对应第 3 页。",
        misconceptions=[
            [("20", "只算了 8:20 到 8:40，没有算到 9:00。", "先补到整时再加余下的分钟。"),
             ("80", "把起止时刻相加当成了经过时间。", "经过时间要用结束时刻减开始时刻。")],
            [("45", "把 9:45 当成了时长。", "减去看开始时刻 9:10。"),
             ("25", "把 9:10 看成 9:20 再相减。", "先对齐十位与个位再减。")],
            [("20", "把 10:00 看成 9:80 后少算了 10 分。", "整时相减再加分钟。"),
             ("60", "把 30 分当成了 1 小时。", "1 时=60 分，30 分是半小时。")],
            [("8:20", "8:20 是开始的时刻。", "时刻是时间轴上的一个点。"),
             ("9:00", "9:00 是结束的时刻。", "看它能不能表示“用了多久”。"),
             ("9:45", "9:45 是另一个时刻。", "区分点与段。")]],
        manual=("制作自己的时间小书，保留真实记录和修订；不能用选择题替代作品。",
                ["说明具体材料或步骤", "理由与本条知识相符",
                 "保留实际表现及所用提示，不以模板代替"]),
        source_limit="第 5、7 页原页图像支持作息表中的起止时刻与需要时间两类记录；"
                     "题目中的作息记录为本地自编，未使用书中学生的真实记录。")

    # ------------------------------- 七下英语 Unit 5（p33/37）
    add("english-g7-lower:5:inventory-1", "present-continuous", [33, 37],
        "Present continuous: now and at the moment",
        "Read the sentences and choose the best answer. This unit is about what is "
        "happening now and about making telephone calls.",
        [C("— What ___ you doing at the moment?\n— I’m cleaning my bike.",
           "are", "do", "is", "be", "are"),
         C("— Is Tom reading in his room?\n— No. He ___ basketball with his friends.",
           "is playing", "plays", "play", "is play", "is playing"),
         C("— Are you using the computer now?\n— Yes. I ___ an email to my cousin.",
           "am writing", "write", "is writing", "am write", "am writing"),
         C("Which sentence describes something happening right now?",
           "My sister is watering the flowers in the garden.",
           "My sister waters the flowers every morning.",
           "My sister watered the flowers yesterday.",
           "My sister will water the flowers tomorrow.",
           "My sister is watering the flowers in the garden.")],
        "现在进行时由 be（am/is/are）加动词 -ing 构成，表示此刻正在发生的动作。"
        "主语是 I 用 am，he/she/it 用 is，you/we/they 用 are。疑问句把 be 提到句首，"
        "否定句在 be 后面加 not。看到 now、at the moment、Look! 这类线索，通常用现在"
        "进行时；every morning、yesterday、tomorrow 说明的是习惯、过去或将来。",
        actions=["按主语选 be 动词构成疑问句", "构成第三人称单数的现在进行时",
                 "构成第一人称的现在进行时", "辨认描述当前活动的句子"],
        difficulty="前三项分别考第二人称疑问、第三人称陈述和第一人称陈述，需要同时选对 be "
                   "动词和 -ing 形式；第四项要求在四个时态中只挑出表示“此刻”的一句。",
        review="第 33 页单元目标列出“talk about what is happening by using the present "
               "continuous tense”；第 37 页 Grammar Focus 与 3a、3b 给出 be+doing 的陈述、"
               "疑问与否定形式。四句为本地自编，未抄录教材例句。",
        misconceptions=[
            [("do", "疑问句里要用 be 动词构成进行时。", "看答语中的 I’m doing。"),
             ("is", "主语是 you，要用 are。", "按主语选 be 动词。"),
             ("be", "be 需要随主语变化。", "you 用 are。")],
            [("plays", "这里说的是此刻正在做的事。", "看 No. He… 的语境。"),
             ("play", "进行时不能只用动词原形。", "be 加 -ing。"),
             ("is play", "be 后面要用 -ing 形式。", "play 要变成 playing。")],
            [("write", "进行时要有 be 加 -ing。", "I 用 am，动词加 -ing。"),
             ("is writing", "主语是 I，be 动词用 am。", "按主语选 be。"),
             ("am write", "be 后面要用 -ing 形式。", "write 变成 writing 要去 e。")],
            [("My sister waters the flowers every morning.", "every morning 表示习惯，用一般现在时。",
              "找表示“此刻”的线索。"),
             ("My sister watered the flowers yesterday.", "yesterday 表示过去。", "看时间线索。"),
             ("My sister will water the flowers tomorrow.", "tomorrow 表示将来。",
              "只有一项表示正在进行。")]],
        manual=("模拟打电话，说明自己和同伴正在做什么，并回应信息。",
                ["说明具体材料或步骤", "理由与本条知识相符",
                 "保留实际表现及所用提示，不以模板代替"]),
        source_limit="第 33、37 页支持现在进行时的陈述、疑问与否定形式；句子与情境为本地"
                     "自编，未抄录教材练习。")

    # ------------------------------- 七下英语 Unit 6（p41/45）
    add("english-g7-lower:6:inventory-1", "weather-tenses", [41, 45],
        "Weather: simple present or present continuous",
        "Read the sentences and choose the best answer. This unit is about weather and "
        "weather-related activities.",
        [C("Look! It ___ outside. Take an umbrella.",
           "is raining", "rains", "rain", "is rain", "is raining"),
         C("In my hometown, the sun ___ at around 6 a.m. in summer.",
           "rises", "is rising", "rise", "rising", "rises"),
         C("We usually ___ in when it snows, but now we ___ a snowman outside.",
           "stay … are building", "are staying … build",
           "stay … build", "are staying … are building", "stay … are building"),
         C("Which sentence tells what the weather is like right now?",
           "It is snowing outside.", "It snows a lot here in winter.",
           "It snowed a lot last winter.", "It will snow tomorrow.",
           "It is snowing outside.")],
        "一般现在时表示经常发生或习惯性的动作，常与 usually、often、every winter 连用；"
        "现在进行时表示此刻正在发生或正在变化的天气，常与 now、right now、Look! 连用。"
        "同一段话里可以先说习惯、再说此刻：“We usually stay in when it snows, but now "
        "we are building a snowman outside.” 主语第三人称单数的一般现在时，动词要加 -s。",
        actions=["用现在进行时描述此刻的天气", "用一般现在时描述常年规律",
                 "在同一句中区分习惯与此刻", "辨认描述当前天气的句子"],
        difficulty="前三项要在同一语法点上切换两种时态：第二项看“in summer”这一习惯线索，"
                   "第三项一句里两个空分别用一般现在时和现在进行时，第四项只挑出“此刻”。",
        review="第 41 页单元目标列出用现在进行时和一般现在时谈天气活动；第 45 页 Grammar "
               "Focus 与 3a、3b 给出两种时态的对照例句。四句为本地自编，未抄录教材练习。",
        misconceptions=[
            [("rains", "Look! 提示此刻正在下雨。", "看叹词与“现在”的线索。"),
             ("rain", "进行时不能只用动词原形。", "It 后面用 is raining。"),
             ("is rain", "be 后面要用 -ing 形式。", "rain 要变成 raining。")],
            [("is rising", "in summer 表示常年的规律。", "习惯性动作用一般现在时。"),
             ("rise", "主语 the sun 是第三人称单数。", "一般现在时动词加 -s。"),
             ("rising", "缺少谓语动词。", "选择完整的时态形式。")],
            [("are staying … build", "前半句是习惯，后半句是此刻，时态用反了。",
              "usually 配一般现在时，now 配现在进行时。"),
             ("stay … build", "后半句有 now，要用现在进行时。", "看 now 这一线索。"),
             ("are staying … are building", "前半句有 usually，应用一般现在时。",
              "按 usually 与 now 分别选时态。")],
            [("It snows a lot here in winter.", "这一句说的是冬天的习惯。", "找“此刻”的线索。"),
             ("It snowed a lot last winter.", "这一句说的是去年冬天。", "看时间状语。"),
             ("It will snow tomorrow.", "这一句说的是明天。", "只有一句表示现在。")]],
        manual=("介绍一个天气情境及相应安排，与同伴交换并回应建议。",
                ["说明具体材料或步骤", "理由与本条知识相符",
                 "保留实际表现及所用提示，不以模板代替"]),
        source_limit="第 41、45 页支持天气词汇与两种时态的对照；句子与情境为本地自编，"
                     "未抄录教材练习。")

    # ------------------------------- 七下英语 Unit 7（p49/53）
    add("english-g7-lower:7:inventory-1", "simple-past", [49, 53],
        "Simple past: school trips and diaries",
        "Read the sentences and choose the best answer. This unit is about past events "
        "and diary entries.",
        [C("Yesterday Peter ___ up at 5 a.m.", "got", "gets", "get", "is getting", "got"),
         C("— Did you visit the space museum last week?\n— Yes, I ___.",
           "did", "do", "was", "am", "did"),
         C("Last month our class ___ on a school trip to the science museum.",
           "went", "goes", "go", "is going", "went"),
         C("— How was your trip?\n— It ___ tiring. I missed the last train.",
           "was", "is", "were", "be", "was")],
        "一般过去时表示过去某个时间发生的动作或存在的状态，常与 yesterday、last week、"
        "last month、a few minutes ago 等连用。规则动词加 -ed，不规则动词要单独记，"
        "如 go—went、get—got、see—saw。一般过去时的疑问句用 did 提问，答语也用 did；"
        "be 动词的过去式是 was/were，主语是 it 时用 was。",
        actions=["用不规则动词的过去式填空", "用 did 回答一般过去时疑问句",
                 "在时间状语提示下用过去式", "用 be 动词的过去式描述状态"],
        difficulty="四项都要先由时间状语判断时态，再选形式：第一、三项考不规则动词，"
                   "第二项考 did 的问答，第四项考 be 动词过去式与主语的配合。",
        review="第 49 页单元目标列出用一般过去时谈过去的事与写日记；第 53 页 Grammar "
               "Focus 与 3a、3b 给出过去时间状语和 did 问答。四句为本地自编，未抄录"
               "教材练习。",
        misconceptions=[
            [("gets", "Yesterday 表示过去，要用过去式。", "看时间状语。"),
             ("get", "过去式不能只用动词原形。", "get 的过去式是 got。"),
             ("is getting", "这是现在进行时。", "按 Yesterday 选过去式。")],
            [("do", "Did 提问要用 did 回答。", "看问句开头的 Did。"),
             ("was", "这里回答的是“有没有去”，不是状态。", "用助动词 did。"),
             ("am", "am 是现在时。", "过去时的答语用 did。")],
            [("goes", "Last month 表示过去。", "看时间状语。"),
             ("go", "过去式要用 went。", "记住 go—went。"),
             ("is going", "这是现在进行时。", "按 Last month 选一般过去时。")],
            [("is", "问句 How was… 已经说明是过去。", "答语也要用过去式。"),
             ("were", "主语是 it，be 动词用 was。", "按主语选 was 或 were。"),
             ("be", "be 要变成过去式。", "it 的过去式是 was。")]],
        manual=("写一篇连贯日记，说明事件与感受；不能由排序题认定完整写作。",
                ["说明具体材料或步骤", "理由与本条知识相符",
                 "保留实际表现及所用提示，不以模板代替"]),
        source_limit="第 49、53 页支持一般过去时的时间状语、不规则动词与 did 问答；"
                     "句子与情境为本地自编，未抄录教材练习。")

    # ------------------------------- 七下英语 Unit 8（p57/61）
    add("english-g7-lower:8:inventory-1", "story-tenses", [57, 61],
        "Story tenses and event order",
        "Read the sentences and choose the best answer. This unit is about telling "
        "stories and making up an ending.",
        [C("When I ___ seven, my favourite story was about a clever fox.",
           "was", "am", "were", "be", "was"),
         C("I usually write stories, but last night I ___ a poem.",
           "wrote", "write", "am writing", "will write", "wrote"),
         C("Long ago, a boy ___ a golden fish in the river, and then he let it go.",
           "caught", "catches", "catch", "is catching", "caught"),
         C("Why did the lion let the mouse go?",
           "Because the mouse promised to help him one day.",
           "Because the mouse was too big to eat.",
           "Because the lion was not hungry at all.",
           "Because the mouse ran away before he could eat it.",
           "Because the mouse promised to help him one day.")],
        "讲故事时，事件发生在过去就用一般过去时：When I was seven…、Last night I wrote…、"
        "Long ago, a boy caught…。表示习惯或普遍情况仍用一般现在时，如 I usually write "
        "stories。判断时态要看时间状语和上下文口径，不能只凭句子长短。叙事还要理清"
        "因果：老鼠请求狮子别吃他，并答应以后帮助狮子，狮子才放他走。",
        actions=["用 be 动词过去式交代故事背景", "在习惯与过去之间切换时态",
                 "用不规则动词过去式叙述事件", "由故事内容判断事件因果"],
        difficulty="前三项都要用时间线索在一般现在时与一般过去时之间选择，第二项一句里"
                   "同时出现 usually 与 last night；第四项要回到故事情节判断因果，而不是"
                   "凭常识猜测。",
        review="第 57 页单元目标列出用一般过去时和一般现在时讲故事、给故事编结尾；第 61 页 "
               "Grammar Focus 与 3a、3b 给出两种时态的对照与老鼠、狮子的情节。四句为"
               "本地自编，未抄录教材练习。",
        misconceptions=[
            [("am", "When I… seven 说的是过去。", "看时间从句。"),
             ("were", "主语是 I，be 动词用 was。", "按主语选 was 或 were。"),
             ("be", "be 要变成过去式。", "I 的过去式是 was。")],
            [("write", "last night 表示过去。", "看时间状语。"),
             ("am writing", "这是现在进行时。", "按 last night 选过去式。"),
             ("will write", "这是将来时。", "write 的过去式是 wrote。")],
            [("catches", "Long ago 表示过去。", "看时间状语。"),
             ("catch", "过去式不能只用原形。", "catch 的过去式是 caught。"),
             ("is catching", "这是现在进行时。", "按 Long ago 选一般过去时。")],
            [("Because the mouse was too big to eat.", "老鼠很小，不是太大。",
              "回到故事中老鼠的请求。"),
             ("Because the lion was not hungry at all.", "故事没有说狮子不饿。",
              "看老鼠答应做了什么。"),
             ("Because the mouse ran away before he could eat it.", "老鼠是被放走的，不是自己逃走的。",
              "看“let him go”之前发生了什么。")]],
        manual=("独立复述或续写故事结尾，保持人物、情节及所选时态一致。",
                ["说明具体材料或步骤", "理由与本条知识相符",
                 "保留实际表现及所用提示，不以模板代替"]),
        source_limit="第 57、61 页支持叙事时态的对照与老鼠、狮子的情节；句子与情境为本地"
                     "自编，未抄录教材练习。")

    # ------------------------------- 七下英语 Reading Plus（p65）
    add("english-g7-lower:9:inventory-1", "reading-plus-octopus", [65],
        "Reading Plus: the amazing octopus",
        "Read the facts below and choose the best answer. This Reading Plus text follows "
        "Unit 1 Animal Friends.",
        [N("Around how many different kinds of octopuses are there?", 300, "300", "kinds"),
         N("How many hearts does an octopus have?", 3, "3", "hearts"),
         C("Why can an octopus fit into small places?",
           "Because it does not have any bones.",
           "Because it has three hearts.",
           "Because it can make ink.",
           "Because it can change colour.",
           "Because it does not have any bones."),
         C("What happens when an octopus loses an arm?",
           "It can grow the arm back.",
           "It can never use its arms again.",
           "It uses its ink to make a new arm.",
           "It takes another octopus’s arm.",
           "It can grow the arm back.")],
        "拓展阅读介绍章鱼：大约有 300 种，最小的约 2.5 厘米，有的能长到 5 米以上。"
        "章鱼有八条腕，脑不只在头部，也分布在腕上，所以能同时思考和做几件事；"
        "它没有骨头，能钻进很小的缝隙；它有三颗心脏。章鱼还能改变颜色和形状、"
        "喷墨躲避天敌，失去一条腕后还能再长出来。这些事实来自同一篇材料，"
        "回答时要回到原文核对，不要凭印象补充。",
        actions=["从材料中读出种类数量", "从材料中读出心脏数量",
                 "由身体结构解释钻缝能力", "从材料中读出再生能力"],
        difficulty="两项数值要求回到原文核对（300 种、3 颗心脏），不能与腕的数量混淆；"
                   "两项选择要求把结构特点与功能对应起来，区分“没有骨头”“变色”“喷墨”"
                   "各自解释什么。",
        review="300 种、八条腕、无骨头、三颗心脏、断腕可再生均取自第 65 页原文；"
               "该材料标为 Unit 1 的 Reading Plus，与本单元动物主题直接相连。",
        misconceptions=[
            [("8", "8 是腕的条数，不是种类数。", "看“different kinds”问的是什么。"),
             ("3", "3 是心脏的数量。", "区分种类、腕和心脏三个数字。")],
            [("8", "8 是腕的条数。", "看“hearts”这个关键词。"),
             ("2", "章鱼有三颗心脏。", "回到原文的数字。")],
            [("Because it has three hearts.", "心脏数量与钻缝能力无关。", "找身体结构方面的原因。"),
             ("Because it can make ink.", "喷墨用于躲避天敌。", "看“no bones”。"),
             ("Because it can change colour.", "变色用于伪装，不是钻缝的原因。",
              "回到“fit into small places”。")],
            [("It can never use its arms again.", "材料说失去的腕能再长出来。",
              "看最后一段的事实。"),
             ("It uses its ink to make a new arm.", "墨汁不能长出腕。", "区分墨汁与再生。"),
             ("It takes another octopus’s arm.", "材料没有这样说。", "回到原文的再生说明。")]],
        manual=("选择一段材料解释主旨与支持细节；后续篇目逐篇复核。",
                ["说明具体材料或步骤", "理由与本条知识相符",
                 "保留实际表现及所用提示，不以模板代替"]),
        source_limit="第 65 页支持章鱼的种类数、腕、心脏、无骨头、变色、喷墨与再生等事实；"
                     "题目只考可核对的事实，不要求复述全文。")

    return {"format": "dd-family-chapter-practice-v1", "batch": BATCH,
            "status": "local_candidate_not_registered", "teacher_reviewed": False,
            "curriculum_standard_crosscheck": "pending", "student_calibrated": False,
            "questions": batch.questions}


if __name__ == "__main__":
    data = build()
    raw = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
    if DESTINATION.exists():
        if DESTINATION.read_bytes() != raw:
            raise FileExistsError("Refuse to overwrite a different reviewed candidate")
    else:
        DESTINATION.write_bytes(raw)
    print(f"Local only: {DESTINATION.relative_to(ROOT)} "
          f"({len(data['questions'])} candidates; not registered)")
