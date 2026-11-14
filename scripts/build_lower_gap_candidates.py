"""Author lower-book first-scope candidates, without registering or installing them.

Only writes a new local JSON on explicit invocation. No application, database,
provider, OCR or deployment entry point is imported. Review/export is separate.
"""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from knowledge_task_authoring import KnowledgeTasks, C, N, E, table as T

ROOT = Path(__file__).resolve().parents[1]
BATCH = "lower_gap_candidates"
DESTINATION = ROOT / "learning_service/data/family_chapter_lower_gap_candidates_v1.json"
DEFAULT_SOURCE_LIMIT = "固定原页只作主题与学科事实依据；题目、材料与数据为本地自编。"


def build():
    batch = KnowledgeTasks(BATCH)

    def add(point, key, pages, title, prompt, fields, explanation, *, actions,
            difficulty, review, misconceptions=(), role="direct", manual=None,
            visual=None, source_limit=DEFAULT_SOURCE_LIMIT):
        """Author one reviewed candidate; bind misconceptions to real wrong answers."""
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
                    index = field["options"].index(text)
                    assert str(index + 1) != field["answer"], (point, key, text)
                    errors.append(E(str(index + 1), message, action))
                elif field["kind"] == "number":
                    assert text != field["answer"], (point, key, text)
                    errors.append(E(text, message, action))
                else:
                    # Text answers carry their own misconception strings verbatim.
                    assert field["kind"] == "text", (point, key, field["kind"])
                    assert text not in field["accepted"], (point, key, text)
                    errors.append(E(text, message, action))
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

    # ---------------------------------------------------------------- 二下数学
    add("math-g2-lower:1:inventory-1", "remainder-identity", [11, 12, 15],
        "摆小棒求商、余数与检验",
        "用小棒摆五边形，每个五边形用5根小棒。现在有23根小棒，摆到不能再摆为止。"
        "下面的判断都只用题中给出的数量。",
        [N("能摆成几个五边形？", 4, "(23-3)/5", "个"),
         N("还剩几根小棒？", 3, "23-5*4", "根"),
         C("哪个算式的写法符合“余数必须小于除数”？",
           "17÷5=3……2",
           "17÷5=2……7", "17÷5=3……2", "17÷5=4……−3"),
         C("用“被除数=除数×商+余数”检验 26÷4=6……2，结论是哪个？",
           "成立，因为4×6+2=26",
           "不成立，因为26不能被4整除", "成立，因为4×6=24", "成立，因为4×6+2=26")],
        "23÷5=4余3：4个五边形用去20根，剩3根，且3<5。检验要用除数×商+余数还原被除数，"
        "4×6+2=26成立；只算4×6=24不是完整检验。余数等于或大于除数、余数为负，都不是正确的写法。",
        actions=["由分组求商", "由分组求余数", "检查余数小于除数", "用关系式还原被除数"],
        difficulty="同一情境里同时求商、求余数、检查约束并验算，四项全部正确才算本题答对。",
        review="23÷5=4…3与26÷4=6…2独立复算；错误选项分别违反余数范围或漏掉余数；"
               "题目自编，未使用教材原题或插图。",
        misconceptions=[
            [("5", "商超过了实际能摆出的个数。", "先算5×4，再比较剩余根数。")],
            [("2", "余数应等于总根数减去已用根数。", "从23中减去5×4。")],
            [("17÷5=2……7", "余数7不小于除数5。", "余数必须小于除数。"),
             ("17÷5=4……−3", "余数不能是负数。", "余数表示剩下没分完的部分。")],
            [("成立，因为4×6=24", "只算了除数×商，漏掉余数。", "把余数也加回去还原被除数。"),
             ("不成立，因为26不能被4整除", "有余数除法本来就允许不整除。", "用关系式检验，而不是判断能否整除。")]])

    add("math-g2-lower:1:inventory-2", "remainder-in-context", [19],
        "余数要不要再多算一份",
        "两个情境各只有一种问法：22枝玫瑰每5枝扎一束；40个鸡蛋每盒最多装6个。"
        "分别判断要算“完整的组数”“剩下的数量”，还是“至少要几个容器”。",
        [N("22枝玫瑰，每5枝扎一束，最多能扎几束？", 4, "(22-2)/5", "束"),
         N("22枝玫瑰按上面扎法，还剩几枝？", 2, "22-5*4", "枝"),
         N("40个鸡蛋，每盒最多装6个，全部装完至少要几个盒子？", 7, "(40-4)/6+1", "个"),
         C("哪个问题必须把余数再多算一份？",
           "40个鸡蛋每盒最多装6个，至少要几个盒子",
           "22枝玫瑰每5枝扎一束，最多扎几束", "17个草莓平均分给3只刺猬，每只分几个",
           "40个鸡蛋每盒最多装6个，至少要几个盒子")],
        "22÷5=4余2：能扎4整束，剩2枝，2枝不够一束，不多算。40÷6=6余4：装满6盒后还剩4个，"
        "仍需再装一盒，至少7盒。剩下的部分能不能单独成一份，决定余数是否再多算一次。",
        actions=["求完整组数", "求剩余数量", "求至少所需容器数", "判断何时余数要多算一份"],
        difficulty="同一页面上的三类问法同时出现，需逐题判断余数的处理方式。",
        review="22÷5、40÷6独立复算；四个选项对应四种不同问法，正确答案唯一；"
               "数据为自编，未使用教材原题。",
        misconceptions=[
            [("5", "剩下的2枝不够一束，不能多算一束。", "先算5×4，再比较剩余枝数。")],
            [("3", "余数等于总枝数减去已用枝数。", "从22中减去5×4。")],
            [("6", "装满6盒后还剩4个，还要再装一盒。", "余数不为0时容器数要加1。")],
            [("17个草莓平均分给3只刺猬，每只分几个", "这是求每份多少，不涉及容器数。", "区分“每份多少”和“要几个容器”。"),
             ("22枝玫瑰每5枝扎一束，最多扎几束", "问的是最多几整束，剩下的不够一束。", "看清问的是组数、余数还是容器数。")]])

    # ---------------------------------------------------------------- 七下英语
    add("english-g7-lower:1:inventory-1", "animal-card-facts", [2, 4, 5],
        "Animal card: facts and the reason",
        "Read the card (written for this exercise, not taken from the textbook), then answer.\n"
        "Name: snow leopard. Looks: thick grey fur with dark spots and a long tail. "
        "Home: high mountains in Asia. Food: wild sheep and other small animals. "
        "Ability: it can jump far and climb steep rocks. "
        "People like it because it is quiet and strong.",
        [C("Which sentence gives BOTH the home and the ability on the card?",
           "It lives in high mountains and can jump far.",
           "It lives in the sea and can swim fast.",
           "It lives in high mountains and can jump far.",
           "It lives on farms and cannot climb."),
         C("Which words describe its looks on the card?",
           "thick grey fur and a long tail",
           "green feathers and a short beak", "thick grey fur and a long tail",
           "white wool and small ears"),
         C("What does it eat on the card?",
           "wild sheep and other small animals",
           "fish and sea animals", "leaves and grass only",
           "wild sheep and other small animals"),
         {"kind": "text", "label": "Why do people like it? Answer with “Because …”",
          "answer": "Because it is quiet and strong.",
          "accepted": ["Because it is quiet and strong.", "Because it is quiet and strong",
                       "Because it's quiet and strong.", "Because it's quiet and strong"],
          "case_sensitive": False, "units": [], "options": [], "errors": []}],
        "The card gives looks, home, food, ability and one reason. Only one option in each "
        "question matches what the card says, and the home-and-ability sentence must keep both "
        "facts together. A “Because …” answer repeats the reason on the card. Choosing these "
        "does not show that you can describe an animal yourself.",
        actions=["匹配栖息地与能力", "匹配外形", "匹配食物", "用because说出卡片上的理由"],
        difficulty="四项都回到同一张资料卡逐条对应，含一个限定句式与拼写的短答。",
        review="卡片为自编材料，三项选择与一项短答逐条对照卡片文字；because项接受句号与"
               "it is / it's 共四种写法，不接受其他理由。朗读与自主介绍不在本题范围。",
        misconceptions=[
            [("It lives in the sea and can swim fast.", "卡片写的是高山，不是海洋。", "回到Home一行核对。")],
            [("white wool and small ears", "卡片写的是浓密灰色毛皮和长尾。", "回到Looks一行核对。")],
            [("fish and sea animals", "卡片写的是野羊等小动物。", "回到Food一行核对。")],
            []],
        source_limit="第2、4、5页支持动物信息卡与why/because问答；卡片内容与选项均为自编，"
                     "未复制教材对话或图片。朗读、听力与自主介绍不在此题范围，须另由人工核对。")

    add("english-g7-lower:1:inventory-2", "plural-and-adjectives", [3, 5],
        "Plurals and describing words",
        "Complete the plurals, then choose the correct sentence and the matching description. "
        "Each item is checked on its own.",
        [{"kind": "text", "label": "Write the plural of “mouse”.",
          "answer": "mice", "accepted": ["mice"],
          "case_sensitive": False, "units": [], "options": [], "errors": []},
         {"kind": "text", "label": "Write the plural of “sheep”.",
          "answer": "sheep", "accepted": ["sheep"],
          "case_sensitive": False, "units": [], "options": [], "errors": []},
         C("Which sentence is correct?",
           "There are three sheep on the hill.",
           "There are three sheeps on the hill.",
           "There are three sheep on the hill.",
           "There is three sheep on the hill."),
         C("The card says: “The fox is small and quick. It has a long tail.” "
           "Which description matches the card?",
           "small and quick", "huge and slow", "small and quick", "big and dangerous")],
        "mouse 的复数是 mice（不规则），sheep 的复数与单数同形；复数主语用 are，"
        "所以“There are three sheep on the hill.”正确。描述只使用卡片上出现的词，"
        "不能凭对动物的印象另加特征。写出词形不等于会读，词尾发音另由人工核对。",
        actions=["写出不规则复数mice", "写出单复数同形的sheep", "选择主谓一致的正确句子",
                 "选择与卡片一致的描述词"],
        difficulty="两个短答含不规则与同形复数，两个选择分别检查主谓一致和资料一致性。",
        review="mice/sheep 两个答案按教材通行口径核对；sheep 复数同形，故带 are 的句子唯一正确；"
               "描述题四个选项与卡片有可判断的差异。",
        misconceptions=[
            [("mouses", "mouse 的复数是不规则形式。", "记住 mouse–mice 这一对。")],
            [("sheeps", "sheep 的复数与单数同形。", "不要给 sheep 加 -s。")],
            [("There are three sheeps on the hill.", "sheep 的复数不加 -s。", "先改词形，再看主谓一致。"),
             ("There is three sheep on the hill.", "复数主语要用 are。", "核对 be 动词与主语是否一致。")],
            [("huge and slow", "卡片写的是 small and quick。", "只使用卡片上出现的词。")]],
        source_limit="第3、5页支持复数词形与形容词描述；词汇与句子为自编，未复制教材词表或练习。"
                     "词尾发音与朗读须另由人工核对，写出词形不等于口语达标。")

    add("english-g7-lower:1:inventory-3", "main-idea-and-details", [6, 7, 8],
        "Main idea, reason and ways to help",
        "Read this short text (written for this exercise).\n"
        "“Many animals live in the forests. People cut down too many trees, so the animals "
        "lose their homes. Some people also catch wild animals for money. We can help. "
        "Do not buy things made from wild animals, and plant trees with your family.”",
        [C("What is the text mainly about?",
           "Why animals lose their homes and how we can help",
           "Why trees are green in spring",
           "Why animals lose their homes and how we can help",
           "How much money hunters make"),
         C("Why do the animals lose their homes, according to the text?",
           "People cut down too many trees.",
           "The animals move away by themselves.",
           "People cut down too many trees.",
           "The forests are too wet in winter."),
         C("Which two ways to help does the text give?",
           "Not buying wild-animal products and planting trees",
           "Catching more animals and cutting more trees",
           "Not buying wild-animal products and planting trees",
           "Buying wild-animal products and cutting trees down"),
         C("Which sentence is a detail in the text, not its main idea?",
           "Some people catch wild animals for money.",
           "Many animals lose their homes and we can help them.",
           "Some people catch wild animals for money.",
           "We should protect animals in the forests.")],
        "短文先说动物需要帮助，再给出两个原因（砍树、为钱捕捉野生动物）和两个做法（不买野生动物制品、种树）。"
        "主旨是把它要讲的问题和做法合起来的概括；某一条具体原因只是细节。四项都要回到短文文字核对，"
        "不能补充短文没有写的内容。",
        actions=["概括短文主旨", "提取动物失去家园的原因", "提取两种保护做法", "区分主旨与细节"],
        difficulty="四项都要求区分概括与原文细节，干扰项把细节说成主旨。",
        review="短文为自编材料，四项答案逐项对应原文；没有把阅读选择题说成写作或口语能力。",
        misconceptions=[
            [("Why trees are green in spring", "短文没有谈树叶颜色。", "主旨要覆盖整段内容。")],
            [("The animals move away by themselves.", "短文说的是人们砍树。", "回到因果句核对。")],
            [("Catching more animals and cutting more trees", "这两种做法会加重问题，不是帮助。", "核对短文说的两件帮助的事。")],
            [("We should protect animals in the forests.", "这句接近概括，不是某一处具体细节。", "细节通常是对某一点的具体说明。")]],
        source_limit="第6、7、8页支持从短文提取问题、原因与保护方法并区分主旨细节；"
                     "短文与题目为自编，未使用教材大象短文原文。阅读理解选择题不代替写作、"
                     "朗读或听力验收。")

    # ---------------------------------------------------------------- 七下生物
    add("biology-g7-lower:1:inventory-1", "germination-conditions-and-design", [2, 3, 4, 5],
        "萌发条件、自身条件与对照设计",
        "纸面练习：判断环境条件、种子自身条件和实验设计。表内数据是编题用的模拟记录，"
        "不是真实实验结果；真实观察另按人工任务核对。",
        [C("下面哪一组都是种子萌发所需要的环境条件？",
           "适宜的温度、适量的水和充足的空气",
           "光照、土壤和肥料",
           "适宜的温度、适量的水和充足的空气",
           "只需要水，其它条件都不影响"),
         C("下面哪种情况属于种子自身条件不具备，而不是环境条件不合适？",
           "种子干瘪，胚已被动物咬坏",
           "培养皿放在冰箱冷藏室",
           "种子干瘪，胚已被动物咬坏",
           "种子完全浸在水中，得不到空气"),
         C("要探究“温度”对萌发的影响，哪个设计能做到只让温度这一个条件不同？",
           "两组种子同样饱满，水和空气相同，只有温度不同",
           "两组温度不同，水量也不同",
           "两组种子同样饱满，水和空气相同，只有温度不同",
           "只做一组，把它放进冰箱冷藏室"),
         N("按表中的模拟记录，适宜温度组三次一共萌发了多少粒？", 27, "9+9+9", "粒")],
        "温度、适量的水和充足的空气是萌发需要的环境条件；干瘪或胚被破坏的种子缺少自身条件，"
        "即使环境适宜也可能不萌发。探究一个条件时只改变它，其余条件与对照组相同。"
        "9+9+9=27 粒只是读表合计，不等于做过实验。",
        visual=T("模拟记录：每格为每组10粒中的萌发粒数（编题数据，不是真实实验结果）",
                 [["组别与条件", "第1次", "第2次", "第3次"],
                  ["适宜温度、适量水、充足空气", "9", "9", "9"],
                  ["低温、适量水、充足空气", "0", "0", "0"]]),
        actions=["辨认萌发的环境条件", "辨认种子自身条件", "辨认单变量对照设计", "读取重复记录"],
        difficulty="四项分别考查条件分类、自身条件、设计原则与记录合计，需在同题区分概念。",
        review="三项环境条件与自身条件按第5页口径核对；对照设计要求只改变温度；9+9+9=27 独立复算。"
               "读表不等于做过实验，故只计辅助并保留人工任务。", role="supporting",
        misconceptions=[
            [("光照、土壤和肥料", "本册列出的萌发环境条件不含这些。", "回到教材总结的三项环境条件。")],
            [("种子完全浸在水中，得不到空气", "这是环境条件不合适（缺氧）。", "区分外部环境与种子本身。")],
            [("两组温度不同，水量也不同", "同时改变了两个条件，无法判断原因。", "一次只改变一个条件。"),
             ("只做一组，把它放进冰箱冷藏室", "没有对照，无法排除种子自身原因。", "设置其余条件相同的对照组。")],
            [("18", "应是三次记录相加，不是两次。", "把三次的9相加。")]],
        manual=("在老师或家长指导下，用安全的种子（如绿豆）设计并实施一次观察：写清只改变的一个条件、"
                "对照组的相同条件、观察间隔与重复次数；如实记录每组萌发数、未萌发数和异常，"
                "未观察的格子留空。不要抄用题中数值。",
                ["只改变预定条件", "说明对照组的相同条件", "逐次记录有时间与单位",
                 "保留未萌发和异常结果", "能说明本次观察的局限"]),
        source_limit="第2—5页支持萌发的环境条件、自身条件、萌发过程与对照实验设计；"
                     "模拟记录与题目为自编，未复制教材实验数据。")

    add("biology-g7-lower:1:inventory-2", "root-growth-and-flower", [8, 9, 16, 17, 18],
        "根尖生长、传粉与受精",
        "把每项功能或过程对应到本册给出的名称。每项只填最直接对应的一项。",
        [C("幼根能不断伸长，主要靠哪两处起作用？",
           "分生区细胞分裂增加数量，伸长区细胞伸长增大体积",
           "根冠细胞不断伸长",
           "分生区细胞分裂增加数量，伸长区细胞伸长增大体积",
           "根毛摆动带动幼根向前伸长"),
         C("根吸收水和无机盐的主要部位是哪里？",
           "成熟区（有大量根毛）",
           "根冠", "成熟区（有大量根毛）", "伸长区"),
         C("“传粉”指的是哪个过程？",
           "花粉从花药散放后落到雌蕊柱头上",
           "花粉管穿过花柱进入子房",
           "花粉从花药散放后落到雌蕊柱头上",
           "精子与卵细胞结合形成受精卵"),
         C("“受精”指的是哪个过程？",
           "精子与卵细胞结合形成受精卵",
           "花粉落到柱头上", "精子与卵细胞结合形成受精卵", "花瓣展开吸引昆虫")],
        "幼根生长一方面靠分生区细胞分裂增加细胞数量，另一方面主要靠伸长区细胞伸长增大细胞体积；"
        "成熟区表皮细胞向外突出形成根毛，是吸收水和无机盐的主要部位。传粉是花粉落到柱头上的过程，"
        "受精是精子与卵细胞结合形成受精卵的过程，两者先后不同、场所不同。",
        actions=["区分分生区与伸长区的作用", "辨认吸收水和无机盐的部位", "辨认传粉过程", "辨认受精过程"],
        difficulty="四项都是成对易混的概念，需按本册定义区分，不能凭日常语感作答。",
        review="根尖各区域功能、传粉与受精定义逐项按第9、17、18页口径核对；"
               "没有把开花等同于结果，也没有把传粉等同于受精。",
        misconceptions=[
            [("根冠细胞不断伸长", "根冠主要起保护作用。", "回到根尖各区域的功能。")],
            [("伸长区", "伸长区主要使细胞体积增大。", "找有大量根毛的区域。")],
            [("花粉管穿过花柱进入子房", "这是花粉管生长，不是传粉。", "传粉发生在柱头上。"),
             ("精子与卵细胞结合形成受精卵", "这是受精，不是传粉。", "区分传粉与受精的先后。")],
            [("花粉落到柱头上", "这是传粉。", "受精发生在胚珠内。")]],
        source_limit="第8—9页支持根尖结构与幼根生长，第16—18页支持花的结构、传粉与受精；"
                     "题目为自编，未复制教材插图。")

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
