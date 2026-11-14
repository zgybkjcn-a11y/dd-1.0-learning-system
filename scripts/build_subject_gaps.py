"""Author focused, bounded tasks for reviewed language-book knowledge gaps."""
from collections import Counter

from knowledge_task_authoring import KnowledgeTasks, W, C, N, E, table as T


batch = KnowledgeTasks("subject_gaps")
add_task = batch.add_task


def add(point, key, page, title, prompt, fields, explanation, *, level="normal", form="语境辨析", visual=None):
    book, chapter, _ = point.split(":", 2)
    family = f"{point}:subject-gaps:{key}"
    add_task(book, chapter, key, page, title, prompt, fields, explanation,
             level=level, form=form, visual=visual, family=family)
    question = batch.questions[-1]
    question["knowledge"]["point_id"] = point
    question["knowledge"]["rationale"] = "题目直接核对本项限定要求；自动结果不代表开放表达或人工任务完成。"
    return question


add(
    "chinese-g2-upper:1:words", "seed-action-context", 11, "动作词放进传播语境",
    "根据句意选择合适的动作词：\n① 有绒毛的蒲公英种子借着风在空中____。\n② 凤仙花果实成熟裂开后，种子会被____周围。",
    [
        C("①", "乘风飘散", "顺水漂走", "挂在动物毛上", "乘风飘散", "留在果壳里"),
        C("②", "弹到", "沉进", "弹到", "随风飘走", "挂在"),
    ],
    "蒲公英带绒毛，适合借风传播；凤仙花果实裂开时会把种子弹出。句子分别给出了传播方式线索。",
    level="normal", form="动作词语境",
)

add(
    "chinese-g2-upper:2:radical", "near-shape-context", 18, "偏旁和句意一起选字",
    "从“晴、清、情、睛”中填字：\n雨停后，天放____了；河水也变得很____。\n再填“清”的偏旁所提示的意思类别。",
    [W("天放____（填一个字）", "晴"), W("河水很____（填一个字）", "清"),
     W("“清”的偏旁提示它与什么有关（填一个字）", "水")],
    "“放晴”写天气转晴；“清”用于河水清澈。日字旁和三点水能提示字义类别，但仍需结合词语语境。",
    level="normal", form="形近字语境辨析",
)

add(
    "chinese-g2-upper:4:dictionary", "radical-stroke-count", 50, "部首笔画和部外笔画",
    "查“桥”字时，已知它由“木”和“乔”组成：“木”4画，“乔”6画。按部首查字法填写笔画数。",
    [C("“桥”的部首", "木", "乔", "氵", "木", "扌"),
     N("部首笔画数", 4, "4"), N("部外笔画数", 6, "6"), N("总笔画数", 10, "4+6")],
    "部首是木，部首本身4画；部首以外的“乔”6画，总笔画为4+6=10。部外笔画不包含部首。",
    level="normal", form="部首查字与笔画核对",
)

add(
    "chinese-g2-upper:9:usage", "common-word-context", 116, "按句意选常用词语",
    "根据句意选择合适的词语：\n① 早读时大家轻声读书，教室里没有吵闹声。\n② 窗户擦干净后，阳光照进教室，房间显得很____。",
    [C("①", "安静", "热闹", "急忙", "安静", "明亮"),
     C("②", "明亮", "安静", "危险", "明亮", "匆忙")],
    "轻声读书、没有吵闹声对应“安静”；阳光照进房间对应“明亮”。词语选择要看句意，不能只按同一主题套词。",
    level="easy", form="词语语境填空",
)

add(
    "chinese-g7-upper:1:poetry", "scene-and-imagination", 15, "诗句中的实景与联想",
    "《观沧海》：“水何澹澹，山岛竦峙。日月之行，若出其中。”只按诗句判断。",
    [C("直接写出的眼前景物", "海水起伏、山岛耸立", "日月真实地沉入海底", "海水起伏、山岛耸立", "星河从海面升出", "海中住着神仙"),
     C("带有想象的诗句画面", "日月仿佛从大海中运行出来", "海水起伏", "山岛耸立", "渔船停在岸边", "日月仿佛从大海中运行出来")],
    "前两句描写水面和山岛；“若出其中”用想象写大海仿佛包容日月，不是说日月真的从海里升起。",
    level="normal", form="诗句证据辨析",
)

add(
    "chinese-g7-upper:2:evidence", "action-supports-feeling", 24, "用动作支持情感判断",
    "自编片段：小晴把伞往弟弟那边移，自己的肩膀被雨淋湿；弟弟说冷，她又把围巾递给弟弟。只按片段判断。",
    [C("最有依据的人物情感", "关心弟弟", "讨厌所有雨天", "关心弟弟", "保证弟弟永远不生病", "不愿意回家"),
     C("最直接支持判断的细节", "把伞偏向弟弟并把围巾给他", "弟弟说冷", "雨正在下", "天气很凉", "把伞偏向弟弟并把围巾给他")],
    "把伞让向弟弟并递出围巾是具体行动，支持她关心弟弟；片段不能证明她对所有雨天的态度。",
    level="normal", form="行动与情感证据",
)

add(
    "english-g7-upper:1:alphabet", "letter-order-spelling", 4, "字母顺序与单词拼写",
    "先按英语字母顺序排列字母，再选出“朋友”的正确拼写。",
    [W("按字母表顺序写出 C、A、B", "A, B, C", "ABC", case_sensitive=False),
     C("“朋友”的正确拼写", "friend", "frend", "friend", "firend", "freind")],
    "A、B、C按字母表顺序排列；friend的拼写依次为f-r-i-e-n-d。",
    level="easy", form="字母顺序与拼读",
)

add(
    "english-g7-upper:3:there", "there-is-are", 13, "用There be描述数量",
    "根据单数或复数名词选择合适的表达。",
    [C("____ one cat on the chair.", "There is", "There are", "It are", "They is", "There is"),
     C("____ two books under the desk.", "There are", "There is", "It is", "They are", "There are")],
    "one cat是单数，用There is；two books是复数，用There are。",
    level="easy", form="There be语境填空",
)

add(
    "english-g7-upper:11:reading", "facts-and-pronouns", 75, "从上下文找事实和代词所指",
    "Read the passage: “Mia borrowed a green book from Ben. She put it beside the window. Before class, Ben asked for the book back, and Mia returned it.”",
    [C("Who does “She” refer to?", "Mia", "Ben", "the teacher", "the book", "Mia"),
     C("What does “it” refer to in “She put it beside the window”?", "the green book", "the window", "Ben", "the class", "the green book"),
     C("Where did Mia put the book?", "beside the window", "under the desk", "in the classroom", "on the bus", "beside the window"),
     C("When did Ben ask for the book back?", "before class", "after school", "at lunch", "on Sunday", "before class")],
    "She指Mia；it指前一句提到的green book。短文明确说她把书放在窗边，Ben在上课前要回书。",
    level="normal", form="篇章事实与指代",
)

add(
    "english-g7-upper:14:be", "be-agreement-and-transforms", 102, "be动词的人称数与句式",
    "按给定句子完成be动词和句式转换。转换只检查语法形式。",
    [C("Ken ____ a student.", "is", "are", "is", "am", "be"),
     C("Ken and Amy ____ classmates.", "are", "is", "am", "are", "be"),
     W("把“Ken is a student.”改成否定句", "Ken is not a student.", "Ken isn't a student.", case_sensitive=False),
     W("把“Ken is a student.”改成一般疑问句", "Is Ken a student?", "Is Ken a student", case_sensitive=False)],
    "Ken是第三人称单数，用is；Ken and Amy是复数，用are。be动词否定在be后加not，一般疑问句把be移到主语前。",
    level="normal", form="be动词句式转换",
)

add(
    "english-g7-upper:14:can", "can-question-and-short-answer", 100, "can疑问句与简答",
    "Facts: Mia can swim. Ben cannot swim. 根据事实写出Can问句，并补全简答。",
    [W("询问Mia是否会游泳", "Can Mia swim?", "Can Mia swim", case_sensitive=False),
     W("Yes, she ____.", "can", case_sensitive=False),
     W("询问Ben是否会游泳", "Can Ben swim?", "Can Ben swim", case_sensitive=False),
     W("No, he ____.", "can't", "cannot", case_sensitive=False)],
    "can构成疑问句时放在主语前，后接动词原形；简答使用can或can't，不随主语改变形式。",
    level="normal", form="can问答",
)

add(
    "english-g7-upper:15:context", "word-form-in-context", 106, "根据句意填写词形",
    "Use the correct form of the word in brackets.\nSam ____ up at seven. (get)\nShe ____ breakfast at home. (have)\nHer friends ____ by bus. (come)",
    [W("get的合适形式", "gets", case_sensitive=False), W("have的合适形式", "has", case_sensitive=False),
     W("come的合适形式", "come", case_sensitive=False)],
    "Sam和She是第三人称单数，动词用gets、has；Her friends是复数，使用come。",
    level="normal", form="单元词汇词形",
)

add(
    "english-g7-upper:16:entry", "dictionary-entry", 113, "按词条选择词性和义项",
    "Mini dictionary entries:\nlight /laɪt/ adj. not heavy; n. brightness.\nplay /pleɪ/ v. take part in a game; n. a drama.",
    [C("In “This bag is light”, light is a ...", "adjective", "noun", "verb", "adjective", "pronoun"),
     C("In “There is light in the room”, light means ...", "brightness", "a game", "weight", "brightness", "a person"),
     C("In “We play a game”, play is a ...", "verb", "noun", "adjective", "verb", "number")],
    "词条给出light的形容词与名词义项、play的动词与名词词性。句中“is light”描述重量，“there is light”表示光，“play a game”是动作。",
    level="normal", form="词典词条语境",
)

add(
    "english-g7-upper:18:calendar", "month-weekday-calendar", 127, "用月份日期和星期核对日历",
    "Use this class calendar for the exercise; follow the card rather than a real-year calendar.",
    [C("March 19 is ...", "Tuesday", "Monday", "Wednesday", "Thursday", "Tuesday"),
     C("The class meeting is on Wednesday. Which date is it?", "March 20", "March 18", "March 19", "March 21", "March 20"),
     W("Write the date in “weekday, month day” order: Wednesday / March 20", "Wednesday, March 20", "Wednesday March 20", case_sensitive=False)],
    "卡片给出March 18 Monday、March 19 Tuesday、March 20 Wednesday。按卡片核对，星期和日期要对应。",
    level="normal", form="月份星期与日期核对",
    visual=T("Class calendar", [["Date", "Weekday"], ["March 18", "Monday"], ["March 19", "Tuesday"], ["March 20", "Wednesday"]]),
)

if __name__ == "__main__":
    print(Counter(question["book_id"] for question in batch.questions))
    batch.write()
