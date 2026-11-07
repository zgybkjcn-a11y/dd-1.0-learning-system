"""Verified edition catalogue; reference retrieval is separate from question approval."""
from copy import deepcopy
import hashlib
import re
import unicodedata
import threading
from pathlib import Path


# Match the exact PDFs used for the vector index; offsets apply only to these files.
PDF_SHA256 = {
    'math-g2-upper': 'df49e1b7465cb6e4f92d97d2f1c7739987f086e7833fe2777bfae9af7fd22d66',
    'math-g7-upper': 'd995a2072c2b00418eacf1fdfc7a00234953592f5fba61a4b227731c8a19fdd8',
    'math-g7-lower': 'eb9bf6ac19ca7756f4587de2e3a842d69f22e1b3ec0ec3b87a795c93fe22257b',
}
_RENDER_LOCK = threading.Lock()  # PyMuPDF document operations are not thread-safe.


SUBJECT_NAMES = {'chinese':'语文','math':'数学','english':'英语','ethics':'道德与法治',
                 'history':'历史','geography':'地理','physics':'物理','chemistry':'化学','biology':'生物'}


def _book(key, grade, semester, file_id, official_id, offset, chapters):
    subject = key.split('-')[0]
    return {'id':key,'grade':grade,'semester':semester,'subject':subject,'subject_title':SUBJECT_NAMES[subject],
            'title':f'人教社{SUBJECT_NAMES[subject]} · {semester}',
            'edition':'依据2022年课标修订的现行新版','verified_on':'2026-11-05',
            'file_id':file_id,'collection':'file-'+file_id,
            'reader_url':f'https://book.pep.com.cn/{official_id}/mobile/index.html',
            'chapters':[{'id':str(i),'title':title,'printed_page':start,
                         'page_start':start+offset,'page_end':end+offset}
                        for i,title,start,end in chapters]}


BOOKS = [
    _book('math-g2-upper',2,'上册','efe6197c-2306-508c-bb81-30ba5db2424c','1221001201251',5,
          [('1','一 分类与整理',1,9),('2','二 1～6的表内乘法',10,29),
           ('3','三 1～6的表内除法',30,48),('activity1','校园小导游',49,54),
           ('4','四 厘米和米',55,67),('activity2','身体上的尺子',68,72),
           ('5','五 7～9的表内乘、除法',73,90),('6','六 复习与关联',91,100)]),
    _book('math-g7-upper',7,'上册','92bca0ee-dea9-5c1e-b283-e1cc90d061c4','1321001101241',7,
          [('1','第一章 有理数',1,23),('2','第二章 有理数的运算',24,67),
           ('3','第三章 代数式',68,87),('4','第四章 整式的加减',88,109),
           ('5','第五章 一元一次方程',110,148),('6','第六章 几何图形初步',149,194)]),
    _book('math-g7-lower',7,'下册','1b01b983-b1a9-5ebf-b488-db2e52a3d5fb','1321001102241',7,
          [('7','第七章 相交线与平行线',1,38),('8','第八章 实数',39,62),
           ('9','第九章 平面直角坐标系',63,86),('10','第十章 二元一次方程组',87,119),
           ('11','第十一章 不等式与不等式组',120,149),('12','第十二章 数据的收集、整理与描述',150,194)]),
    _book('ethics-g2-upper',2,'上册','8ea51941-29a3-5701-ab5e-07f9b24a7b8a','1284001201251',5,
          [('1','第一单元 过好节假日',1,16),('2','第二单元 我爱我们班',17,32),
           ('3','第三单元 我的家乡美',33,48),('4','第四单元 我爱我们的祖国',49,65)]),
]
PDF_SHA256['ethics-g2-upper'] = 'aa412c71473b401f34fee653f2f77d18ef614eea2455c85e32fd3b68f15dbd1c'


# Existing version-verified WebUI collections; page ranges checked against PDF contents.
ADDITIONAL_BOOKS = [{'key': 'chinese-g2-upper',
  'grade': 2,
  'semester': '上册',
  'file_id': 'ea99bdd6-3f54-5dca-8a28-1a4f1cd21cb9',
  'sha256': 'b53ae7565d1b20670df202eb7bacd33fefb675845f57706f34eaeafdc4ad5be9',
  'offset': 5,
  'chapters': [('1', '第一单元·阅读', 1, 15),
               ('2', '第二单元·识字', 16, 27),
               ('3', '第三单元·阅读', 28, 38),
               ('4', '第四单元·阅读', 39, 53),
               ('5', '第五单元·阅读', 54, 66),
               ('6', '第六单元·阅读', 67, 80),
               ('7', '第七单元·阅读', 81, 94),
               ('8', '第八单元·阅读', 95, 107),
               ('9', '识字、写字与词语表', 108, 118)]},
 {'key': 'chinese-g2-lower',
  'grade': 2,
  'semester': '下册',
  'file_id': '740e99d2-bc61-5cd8-81f0-7c529371dc63',
  'sha256': '2884c15b54396a331612bc8294f883320ba6d1dcfbdaf975ecbd86698a46bfab',
  'offset': 5,
  'chapters': [('1', '第一单元·阅读', 1, 14),
               ('2', '第二单元·阅读', 15, 28),
               ('3', '第三单元·识字', 29, 41),
               ('4', '第四单元·阅读', 42, 54),
               ('5', '第五单元·阅读', 55, 68),
               ('6', '第六单元·阅读', 69, 83),
               ('7', '第七单元·阅读', 84, 99),
               ('8', '第八单元·阅读', 100, 112),
               ('9', '识字、写字与词语表', 113, 122)]},
 {'key': 'chinese-g7-upper',
  'grade': 7,
  'semester': '上册',
  'file_id': 'cd281565-9b75-5150-b9e7-8b5c469b666d',
  'sha256': 'b23b7c884609c51c4b9caace7435cde226d01c0b37f321c5ffbf23cbdd89d919',
  'offset': 7,
  'chapters': [('1', '第一单元', 1, 22),
               ('2', '第二单元', 23, 44),
               ('3', '第三单元', 45, 76),
               ('4', '第四单元', 77, 104),
               ('5', '第五单元·活动探究', 105, 130),
               ('6', '第六单元', 131, 156)]},
 {'key': 'chinese-g7-lower',
  'grade': 7,
  'semester': '下册',
  'file_id': 'd0218e6c-9840-5836-88bc-b929c44907c6',
  'sha256': '0974eea39362a8905537f0c1a6c0e23b316fa3328fefa98744572b523383fe3e',
  'offset': 7,
  'chapters': [('1', '第一单元', 1, 26),
               ('2', '第二单元', 27, 58),
               ('3', '第三单元', 59, 94),
               ('4', '第四单元', 95, 120),
               ('5', '第五单元', 121, 142),
               ('6', '第六单元·活动探究', 143, 175)]},
 {'key': 'english-g7-upper',
  'grade': 7,
  'semester': '上册',
  'file_id': '8304d461-76e0-5c64-8a40-2867c88aa482',
  'sha256': '6c51f67ecdbf4104ff6ed5cf36aa97c9ab6b12683407ca506d094598eeee1c2e',
  'offset': 9,
  'chapters': [('1', 'Starter Unit 1 Hello!', 1, 6),
               ('2', 'Starter Unit 2 Keep Tidy!', 7, 12),
               ('3', 'Starter Unit 3 Welcome!', 13, 18),
               ('4', 'Unit 1 You and Me', 19, 26),
               ('5', "Unit 2 We're Family!", 27, 34),
               ('6', 'Unit 3 My School', 35, 42),
               ('7', 'Unit 4 My Favourite Subject', 43, 50),
               ('8', 'Unit 5 Fun Clubs', 51, 58),
               ('9', 'Unit 6 A Day in the Life', 59, 66),
               ('10', 'Unit 7 Happy Birthday!', 67, 74),
               ('11', 'Reading Plus 拓展阅读', 75, 81),
               ('12', 'Listening Scripts 听力材料', 82, 91),
               ('13', 'Pronunciation 语音', 92, 94),
               ('14', 'Grammar 语法', 95, 105),
               ('15', 'Vocabulary in Each Unit 单元词汇', 106, 112),
               ('16', 'Vocabulary A–Z', 113, 118),
               ('17', 'Vocabulary from Primary School 小学词汇', 119, 125),
               ('18', 'Reference Word List 参考词表', 126, 127)]},
 {'key': 'ethics-g7-upper',
  'grade': 7,
  'semester': '上册',
  'file_id': '591fe7de-eb17-59a5-ae43-6311464abf58',
  'sha256': '1a3d34f93331a369b8d060894703f5dff584c2b38e3eefb40e5b49b9d336cad6',
  'offset': 7,
  'chapters': [('1', '第一单元 少年有梦', 1, 24),
               ('2', '第二单元 成长的时空', 25, 58),
               ('3', '第三单元 珍爱我们的生命', 59, 82),
               ('4', '第四单元 追求美好人生', 83, 102)]},
 {'key': 'history-g7-upper',
  'grade': 7,
  'semester': '上册',
  'file_id': 'f0b66cb1-894b-5049-bd84-bbb92179ed3c',
  'sha256': 'e3ede4e845a500271a2941ac56dbb4d33605871e0b0a7be5aee26cd1d04a7f7f',
  'offset': 5,
  'chapters': [('1', '第一单元 史前时期：原始社会与中华文明的起源', 2, 19),
               ('2', '第二单元 夏商周时期', 20, 49),
               ('3', '第三单元 秦汉时期', 50, 89),
               ('4', '第四单元 三国两晋南北朝时期', 90, 118),
               ('5', '活动课与学史方法', 119, 123),
               ('6', '中国古代史大事年表（上）', 124, 125)]},
 {'key': 'geography-g7-upper',
  'grade': 7,
  'semester': '上册',
  'file_id': 'eb68803a-1762-581d-8cb7-4234a3e56ccd',
  'sha256': '00c554e16f476c4a25551314d11e9f20ddeeb6f18d20d3074b3868ab55ce83f7',
  'offset': 5,
  'chapters': [('1', '地理第一课', 1, 4),
               ('2', '第一章 地球', 5, 26),
               ('3', '第二章 地图', 27, 42),
               ('4', '第三章 陆地和海洋', 43, 64),
               ('5', '第四章 天气与气候', 65, 90),
               ('6', '第五章 居民与文化', 91, 108),
               ('7', '第六章 发展与合作', 109, 116),
               ('8', '跨学科主题学习：食料作物传播史', 117, 119),
               ('9', '附录：地图图例', 120, 120)]},
 {'key': 'biology-g7-upper',
  'grade': 7,
  'semester': '上册',
  'file_id': '75b18f63-bba4-5341-b05e-b5acbb4dafaa',
  'sha256': 'a3fa62c010ba830872e4a52354186009495fda15ea5d0668516f7698fe3c7354',
  'offset': 9,
  'chapters': [('1', '第一单元 第一章 认识生物', 1, 11),
               ('2', '第一单元 第二章 认识细胞', 12, 32),
               ('3', '第一单元 第三章 从细胞到生物体', 33, 55),
               ('4', '第二单元 第一章 藻类与植物的类群', 56, 72),
               ('5', '第二单元 第二章 动物的类群', 73, 97),
               ('6', '第二单元 第三章 微生物', 98, 121),
               ('7', '第二单元 第四章 生物分类的方法', 122, 135)]}]
for entry in ADDITIONAL_BOOKS:
    book = _book(entry["key"], entry["grade"], entry["semester"], entry["file_id"], "", entry["offset"], entry["chapters"])
    book.pop("reader_url")
    BOOKS.append(book)
    PDF_SHA256[entry["key"]] = entry["sha256"]

# Printed-page section starts transcribed from these exact PDFs' contents and headings.
# Chapter boundaries below prevent a section label carrying into the next chapter.
SECTION_STARTS = {
    'math-g2-upper': {
        11:'乘法的初步认识',16:'5的乘法口诀',17:'2、3、4的乘法口诀',22:'6的乘法口诀',28:'乘法的整理和复习',
        31:'平均分与除法的初步认识',41:'用2～6的乘法口诀求商',46:'除法的整理和复习',
        65:'厘米和米的整理和复习',73:'7～9的乘法口诀',81:'用7～9的乘法口诀求商',87:'乘、除法的整理和复习',
    },
    'math-g7-upper': {
        2:'正数和负数',6:'用正负数表示允许偏差',7:'有理数的概念',8:'数轴',11:'相反数',13:'绝对值',14:'有理数的大小比较',
        18:'数学史：漫漫长路识负数',20:'有理数的数学活动',21:'有理数的小结与复习',
        25:'有理数的加法',30:'有理数的减法',37:'正负数加减运算法则——正负术',38:'有理数的乘法',43:'有理数的除法',
        50:'探究有理数乘法法则',51:'乘方',54:'科学记数法',55:'近似数',58:'有理数运算的数学活动',59:'有理数运算的小结与复习',63:'进位制的认识与探究',
        69:'列代数式表示数量关系',78:'数字1与字母X的对话',79:'代数式的值',83:'代数式的数学活动',85:'代数式的小结与复习',
        89:'整式',95:'整式的加法与减法',104:'用电子表格进行数据计算',105:'整式加减的数学活动',107:'整式加减的小结与复习',
        111:'从算式到方程',115:'等式的性质',120:'解一元一次方程',132:'无限循环小数化分数',133:'实际问题与一元一次方程',
        142:'初步认识数学模型',143:'一元一次方程的数学活动',145:'一元一次方程的小结与复习',
        150:'几何图形',151:'立体图形与平面图形',155:'点、线、面、体',160:'数学史：几何的起源',162:'直线、射线、线段',
        164:'线段的比较与运算',168:'长度的测量',170:'角的概念',173:'角的比较与运算',176:'余角和补角',180:'角的度量',
        182:'几何图形的数学活动',184:'几何图形的小结与复习',189:'设计学校田径运动会比赛场地',
    },
    'math-g7-lower': {
        2:'两条直线相交',3:'两条直线垂直',7:'两条直线被第三条直线所截',10:'观察与猜想：看图时的错觉',11:'平行线的概念',
        13:'平行线的判定',15:'平行线的性质',22:'定义、命题、定理',26:'平移',30:'利用平移设计图案',32:'相交线与平行线的数学活动',34:'相交线与平行线的小结与复习',
        40:'平方根',48:'立方根',52:'实数及其简单运算',58:'为什么根号2不是有理数',59:'实数的数学活动',60:'实数的小结与复习',
        64:'平面直角坐标系的概念',67:'用坐标描述简单几何图形',71:'用经纬度表示地理位置',72:'用坐标表示地理位置',74:'用坐标表示平移',82:'坐标系的数学活动',83:'坐标系的小结与复习',
        88:'二元一次方程组的概念',91:'代入消元法',95:'加减消元法',101:'实际问题与二元一次方程组',107:'三元一次方程组的解法',
        112:'中国古代解多元一次方程组',114:'中国古代的一次不定方程组问题',115:'方程组的数学活动',117:'方程组的小结与复习',
        121:'不等式及其解集',123:'不等式的性质',130:'用求差法比较大小',131:'一元一次不等式',138:'一元一次不等式组',
        142:'不等式的数学活动',143:'不等式的小结与复习',146:'综合与实践：低碳生活',
        151:'全面调查',153:'抽样调查',159:'探究瓶子中豆子的数量',160:'扇形图、条形图和折线图',165:'直方图',171:'趋势图',
        178:'利用信息技术工具画统计图',180:'数学史：统计学点滴',182:'统计的数学活动',183:'统计的小结与复习',188:'白昼时长规律的探究',
    },
}
SECTION_STARTS.update({'chinese-g2-upper': {1: '课文：小蝌蚪找妈妈',
                      5: '课文：我是什么',
                      8: '课文：植物妈妈有办法',
                      11: '语文园地一',
                      15: '快乐读书吧：童话故事',
                      16: '识字：场景歌',
                      18: '识字：树之歌',
                      20: '识字：拍手歌',
                      23: '识字：田家四季歌',
                      25: '语文园地二',
                      28: '课文：彩虹',
                      30: '课文：去外婆家',
                      32: '课文：数星星的孩子',
                      35: '语文园地三',
                      39: '古诗：登鹳雀楼',
                      40: '古诗：望庐山瀑布',
                      42: '课文：黄山奇石',
                      45: '课文：日月潭',
                      47: '课文：葡萄沟',
                      50: '语文园地四',
                      54: '寓言：坐井观天',
                      56: '课文：寒号鸟',
                      60: '课文：我要的是葫芦',
                      63: '语文园地五',
                      67: '课文：八角楼上',
                      69: '课文：朱德的扁担',
                      72: '课文：难忘的泼水节',
                      75: '课文：刘胡兰',
                      78: '语文园地六',
                      81: '古诗：江雪',
                      82: '古诗：敕勒歌',
                      84: '课文：雾在哪里',
                      87: '课文：雪孩子',
                      91: '语文园地七',
                      95: '课文：称赞',
                      98: '课文：纸船和风筝',
                      101: '课文：快乐的小河',
                      104: '语文园地八',
                      108: '识字表',
                      113: '写字表',
                      116: '词语表'},
 'chinese-g2-lower': {1: '古诗：咏柳',
                      2: '古诗：村居',
                      4: '课文：找春天',
                      6: '课文：开满鲜花的小路',
                      9: '课文：邓小平爷爷植树',
                      11: '语文园地一',
                      15: '课文：雷锋叔叔，你在哪里',
                      18: '课文：千人糕',
                      21: '课文：我不是最弱小的',
                      24: '语文园地二',
                      28: '快乐读书吧：儿童故事',
                      29: '识字：神州谣',
                      31: '识字：传统节日',
                      33: '识字：“贝”的故事',
                      35: '识字：中国美食',
                      37: '语文园地三',
                      42: '课文：彩色的梦',
                      45: '课文：一匹出色的马',
                      48: '课文：枫树上的喜鹊',
                      51: '语文园地四',
                      55: '寓言：亡羊补牢',
                      56: '寓言：揠苗助长',
                      58: '课文：画杨桃',
                      61: '课文：小马过河',
                      65: '语文园地五',
                      69: '古诗：绝句',
                      70: '古诗：晓出净慈寺送林子方',
                      72: '课文：雷雨',
                      74: '课文：要是你在野外迷了路',
                      77: '课文：太空生活趣事多',
                      79: '语文园地六',
                      84: '课文：大象的耳朵',
                      87: '课文：蜘蛛开店',
                      90: '课文：青蛙卖泥塘',
                      94: '课文：小毛虫',
                      97: '语文园地七',
                      100: '神话：羿射九日',
                      103: '课文：黄帝的传说',
                      106: '课文：大禹治水',
                      109: '语文园地八',
                      113: '识字表',
                      117: '写字表',
                      120: '词语表'},
 'chinese-g7-upper': {2: '课文：春',
                      6: '课文：济南的冬天',
                      10: '课文：雨的四季',
                      15: '古代诗歌四首',
                      18: '阅读综合实践',
                      20: '写作：热爱写作，学会观察',
                      24: '课文：秋天的怀念',
                      27: '课文：散步',
                      30: '散文诗二首',
                      34: '文言文：《世说新语》二则',
                      37: '阅读综合实践',
                      39: '写作：学会记事',
                      41: '专题：有朋自远方来',
                      46: '课文：从百草园到三味书屋',
                      53: '课文：往事依依',
                      57: '课文：再塑生命的人',
                      62: '文言文：《论语》十二章',
                      66: '阅读综合实践',
                      68: '写作：如何突出中心',
                      71: '整本书阅读：《朝花夕拾》',
                      75: '课外古诗词诵读',
                      78: '课文：纪念白求恩',
                      82: '课文：回忆我的母亲',
                      88: '诗歌：梅岭三章',
                      91: '文言文：诫子书',
                      93: '阅读综合实践',
                      95: '写作：思路要清晰',
                      98: '专题：少年正是读书时',
                      106: '活动探究：人与动物',
                      108: '课文：猫',
                      113: '课文：我的白鸽',
                      120: '课文：大雁归来',
                      125: '文言文：狼',
                      127: '活动：亲近动物',
                      129: '写作：记叙与动物的相处',
                      132: '课文：小圣施威降大圣',
                      136: '童话：皇帝的新装',
                      142: '神话：女娲造人',
                      146: '寓言四则',
                      150: '阅读综合实践',
                      151: '写作：发挥联想和想象',
                      154: '整本书阅读：《西游记》',
                      155: '课外古诗词诵读'},
 'chinese-g7-lower': {2: '课文：邓稼先',
                      9: '课文：说和做',
                      13: '课文：列夫·托尔斯泰',
                      20: '文言文：孙权劝学',
                      22: '阅读综合实践',
                      24: '写作：写出人物特点',
                      28: '诗歌：黄河颂',
                      31: '课文：老山界',
                      36: '课文：谁是最可爱的人',
                      42: '课文：土地的誓言',
                      46: '古诗：木兰诗',
                      49: '阅读综合实践',
                      51: '写作：学习抒情',
                      54: '专题：我的语文生活',
                      60: '课文：阿长与《山海经》',
                      67: '课文：山地回忆',
                      74: '课文：台阶',
                      82: '文言文：卖油翁',
                      84: '阅读综合实践',
                      86: '写作：抓住细节',
                      89: '整本书阅读：《骆驼祥子》',
                      93: '课外古诗词诵读',
                      96: '课文：驿路梨花',
                      101: '课文：青春之光',
                      108: '课文：有为有不为',
                      111: '文言文：陋室铭、爱莲说',
                      114: '阅读综合实践',
                      115: '写作：怎样选材',
                      118: '专题：孝亲敬老，传承家风',
                      122: '课文：井冈翠竹',
                      127: '课文：紫藤萝瀑布',
                      130: '外国诗二首',
                      133: '古代诗歌五首',
                      137: '阅读综合实践',
                      139: '写作：语言要简明',
                      142: '整本书阅读：《钢铁是怎样炼成的》',
                      144: '活动探究：阅读与探讨',
                      145: '课文：太空一日',
                      156: '课文：“蛟龙”探海',
                      161: '科幻：带上她的眼睛',
                      169: '文言文：活板',
                      172: '活动：搜集与整理',
                      173: '活动：表达与呈现',
                      174: '课外古诗词诵读'},
 'ethics-g7-upper': {2: '开启初中生活：奏响中学序曲',
                     6: '规划初中生活',
                     9: '认识自己',
                     12: '做更好的自己',
                     16: '做有梦想的少年',
                     19: '学习成就梦想',
                     23: '单元思考与行动',
                     26: '家的意味',
                     29: '让家更美好',
                     34: '走近老师',
                     37: '珍惜师生情谊',
                     42: '友谊的真谛',
                     45: '交友的智慧',
                     50: '集体生活成就我',
                     53: '共建美好集体',
                     57: '单元思考与行动',
                     60: '认识生命',
                     63: '敬畏生命',
                     67: '增强安全意识',
                     70: '提高防护能力',
                     74: '爱护身体',
                     77: '滋养心灵',
                     81: '单元思考与行动',
                     84: '探问人生目标',
                     86: '树立正确的人生目标',
                     90: '拥有积极的人生态度',
                     92: '正确对待顺境和逆境',
                     95: '在劳动中创造人生价值',
                     97: '在奉献中成就精彩人生',
                     101: '单元思考与行动'},
 'history-g7-upper': {4: '远古时期的人类活动',
                      9: '原始农业与史前社会',
                      15: '中华文明的起源',
                      22: '夏商西周王朝的更替',
                      28: '动荡变化中的春秋时期',
                      33: '战国时期的社会变革',
                      39: '百家争鸣',
                      44: '夏商周时期的科技与文化',
                      52: '秦统一中国',
                      58: '秦末农民大起义',
                      63: '西汉建立和“文景之治”',
                      67: '大一统王朝的巩固',
                      73: '东汉的兴衰',
                      78: '丝绸之路的开通与经营西域',
                      84: '秦汉时期的科技与文化',
                      92: '三国鼎立',
                      98: '西晋的短暂统一和北方各族的内迁',
                      102: '东晋南朝政治和江南地区开发',
                      107: '北朝政治和北方民族大交融',
                      113: '三国两晋南北朝时期的科技与文化',
                      119: '活动：从考古发现看中华文明的起源',
                      121: '学史方法：出土文物中的信息',
                      122: '学史方法：历史纪年法',
                      123: '学史方法：阅读历史地图',
                      124: '中国古代史大事年表'},
 'geography-g7-upper': {6: '地球的宇宙环境',
                        11: '地球与地球仪',
                        21: '地球的运动',
                        28: '地图的阅读',
                        32: '地形图的判读',
                        37: '地图的选择和应用',
                        41: '跨学科主题学习：美化校园',
                        44: '大洲和大洋',
                        52: '世界的地形',
                        57: '海陆的变迁',
                        66: '多变的天气',
                        72: '气温的变化与分布',
                        79: '降水的变化与分布',
                        84: '世界的气候',
                        92: '人口与人种',
                        98: '城镇与乡村',
                        103: '多样的文化'},
 'biology-g7-upper': {2: '观察周边环境中的生物',
                      7: '生物的特征',
                      12: '实验：学习使用显微镜',
                      18: '植物细胞',
                      23: '动物细胞',
                      28: '细胞的生活',
                      33: '细胞通过分裂产生新细胞',
                      38: '动物体的结构层次',
                      43: '植物体的结构层次',
                      46: '单细胞生物',
                      51: '实践项目：制作细胞模型',
                      53: '单元小结',
                      54: '复习与提高',
                      58: '藻类、苔藓植物和蕨类植物',
                      65: '种子植物',
                      73: '无脊椎动物',
                      79: '脊椎动物：鱼',
                      85: '两栖动物和爬行动物',
                      90: '鸟和哺乳动物',
                      98: '微生物的分布',
                      103: '细菌',
                      109: '真菌',
                      114: '病毒',
                      120: '实践项目：制作发酵食品',
                      122: '尝试对生物进行分类',
                      127: '从种到界',
                      133: '单元小结',
                      134: '复习与提高'}})
PAGE_TITLES = {
    ('math-g7-upper',115): '一元一次方程的定义与等式的性质',
    ('math-g7-upper',144): '杠杆平衡探究：列一元一次方程',
    ('chinese-g7-upper',1): '第一单元导读：四季美景与朗读',
    ('chinese-g7-upper',23): '第二单元导读：亲情与情感表达',
    ('chinese-g7-upper',45): '第三单元导读：学习、成长与默读',
    ('chinese-g7-upper',77): '第四单元导读：理想、人格与人生价值',
    ('chinese-g7-upper',105): '第五单元活动探究：人与动物',
    ('chinese-g7-upper',131): '第六单元导读：想象与文学世界',
    ('chinese-g7-lower',1): '第一单元导读：杰出人物与精读',
    ('chinese-g7-lower',27): '第二单元导读：家国情怀与抒情',
    ('chinese-g7-lower',59): '第三单元导读：平凡人物与人性之美',
    ('chinese-g7-lower',95): '第四单元导读：中华美德与略读',
    ('chinese-g7-lower',121): '第五单元导读：托物言志与比较阅读',
    ('chinese-g7-lower',143): '第六单元活动探究：科学精神与科技成就',
}
SECTION_STARTS['ethics-g2-upper'] = {
    2:'假期有收获',6:'教师节快乐',9:'团团圆圆过中秋',13:'欢欢喜喜庆国庆',
    18:'这是我们班',22:'班级生活有规则',26:'我是班级值日生',29:'我为班级作贡献',
    34:'我爱家乡山和水',38:'家乡物产养育我',41:'可亲可敬的家乡人',45:'家乡新变化',
    50:'美丽中国我们的家',54:'我们都是中国人',58:'红红火火中国年',62:'祖国，我为您自豪',
}


def page_title(book, chapter, printed_page, text):
    if not chapter['id']:
        chapter = next(c for c in book['chapters'] if c['printed_page'] <= printed_page <=
                       c['printed_page'] + c['page_end'] - c['page_start'])
    explicit = PAGE_TITLES.get((book['id'], printed_page))
    if explicit:
        return explicit
    starts = {page:title for page,title in SECTION_STARTS.get(book['id'], {}).items()
              if chapter['printed_page'] <= page <= printed_page}
    title = starts[max(starts)] if starts else chapter['title']
    normalized = unicodedata.normalize('NFKC', text)
    # Only explicit standalone labels add a page type; do not summarize garbled formulas.
    if re.search(r'(?m)^\s*例\s*\d', normalized):
        title += ' · 例题'
    elif re.search(r'(?m)^\s*(?:练习|做一做)(?:\s|[一二三四五六七八九十\d]|$)', normalized):
        title += ' · 练习'
    return title


def catalogue(curriculum_id):
    grade = {'math-g2-v1':2,'math-g7-v1':7}.get(curriculum_id)
    return deepcopy([book for book in BOOKS if book['grade']==grade])


def practice_scope(question_version_id):
    """Explicit placements of existing authored versions, never inferred from OCR.

    G2: 3x4 uses 1-6 tables; 6x7, 8x5 and 9x9 use 7-9 tables.
    G7: subtracting a negative belongs to rational-number operations (chapter 2).
    The four old addition/subtraction questions have no placement in this edition.
    """
    from .practice import placement
    curated = placement(question_version_id)
    if curated: return curated
    for objective, count, book in [
        ('objective-math-g2-multiplication', 4, 'math-g2-upper'),
        ('objective-math-g7-subtract-negative-v1', 6, 'math-g7-upper'),
    ]:
        for index in range(1, count + 1):
            if question_version_id == f'family-starter-{objective}-{index}-v1':
                return {'book_id': book, 'chapter_id': '2' if index == 1 or book == 'math-g7-upper' else '5'}
    return None


def learning_scope(curriculum_id, book_id, chapter_id=None):
    book = next((b for b in catalogue(curriculum_id) if b['id'] == book_id), None)
    if not book:
        raise ValueError('book outside current grade')
    if chapter_id is None or chapter_id == '':
        first, last = book['chapters'][0], book['chapters'][-1]
        return book, {'id': '', 'title': '整本书', 'printed_page': first['printed_page'],
                      'page_start': first['page_start'], 'page_end': last['page_end']}
    chapter = next((c for c in book['chapters'] if c['id'] == chapter_id), None)
    if not chapter:
        raise ValueError('chapter unavailable')
    return book, chapter


def subject_catalogue(curriculum_id):
    books = catalogue(curriculum_id)
    if not books:
        return []
    applicable = ['chinese','math','ethics'] if books[0]['grade']==2 else ['chinese','math','english','ethics','history','geography','biology']
    return [{'id':subject,'title':SUBJECT_NAMES[subject],
             'available':any(b['subject']==subject for b in books),
             'notice': '新版教材待补齐' if not any(b['subject']==subject for b in books) else
                       '下册正在核验，暂未开放检索' if subject=='math' and books[0]['grade']==2 else
                       '目前已接入上册，下册待补齐' if not any(b['subject']==subject and b['semester']=='下册' for b in books) else ''}
            for subject in applicable]


def search_scope(curriculum_id, body):
    if not isinstance(body,dict) or set(body)-{'book_id','chapter_id','query','page_offset'}:
        raise ValueError('invalid search')
    book,chapter=learning_scope(curriculum_id,body.get('book_id'),body.get('chapter_id'))
    query=body.get('query','')
    if not isinstance(query,str) or len(query)>160 or any(ord(c)<32 for c in query):
        raise ValueError('invalid query')
    offset=body.get('page_offset',0)
    total=chapter['page_end']-chapter['page_start']+1
    if type(offset) is not int or not 0 <= offset < total or (query.strip() and offset):
        raise ValueError('invalid chapter page offset')
    return {'book':book,'chapter':chapter,'query':(chapter['title']+' ' if chapter['id'] else '')+query.strip(),
            'mode':'search' if query.strip() else 'browse','page_offset':offset}


def chapter_references(scope):
    """Read a chapter in physical page order; keywords alone use vector retrieval."""
    book,chapter=scope['book'],scope['chapter']
    total=chapter['page_end']-chapter['page_start']+1
    offset=scope.get('page_offset',0)
    pages=range(chapter['page_start']+offset,min(chapter['page_end']+1,chapter['page_start']+offset+4))
    result=bounded_references(scope,{'documents':[['']*len(pages)],'metadatas':[[{
        'file_id':book['file_id'],'page_number':p,'edition':'pep-2022-standard-current'} for p in pages]]})
    result.update(mode='browse',page_offset=offset,total_pages=total,
        previous_offset=max(0,offset-4) if offset else None,
        next_offset=offset+4 if offset+4<total else None,
        notice=('本章' if chapter['id'] else '本书')+'按页码顺序浏览，每次显示最多4页。点标题展开原页；未经题目审核，不作为标准答案。')
    return result


def page_scope(curriculum_id, book_id, printed_page):
    book = next((b for b in catalogue(curriculum_id) if b['id'] == book_id), None)
    if book and type(printed_page) is int:
        for chapter in book['chapters']:
            pdf_page = printed_page + chapter['page_start'] - chapter['printed_page']
            if chapter['page_start'] <= pdf_page <= chapter['page_end']:
                return book, pdf_page
    raise ValueError('page outside current textbook')


def render_page(directory: Path | None, book_id: str, pdf_page: int) -> bytes:
    """Render the original layout locally, without OCR or extracted-font substitutions."""
    import fitz
    if directory is None or book_id not in PDF_SHA256:
        raise ValueError('textbook source unavailable')
    path = directory / (book_id + '.pdf')
    if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
        raise ValueError('invalid textbook source')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != PDF_SHA256[book_id]:
        raise ValueError('textbook source changed')
    with _RENDER_LOCK:
        with fitz.open(stream=data, filetype='pdf') as document:
            if not 1 <= pdf_page <= len(document):
                raise ValueError('textbook page unavailable')
            return document[pdf_page - 1].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).tobytes('png')


def bounded_references(scope, result):
    """Discard cross-file/edition/chapter chunks, malformed metadata, and excess text."""
    book,chapter=scope['book'],scope['chapter']
    if not isinstance(result,dict):
        raise ValueError('malformed retrieval')
    documents=result.get('documents');metadata=result.get('metadatas')
    if not isinstance(documents,list) or not documents or not isinstance(metadata,list) or not metadata:
        raise ValueError('malformed retrieval')
    if not isinstance(documents[0],list) or not isinstance(metadata[0],list) or len(documents[0])!=len(metadata[0]):
        raise ValueError('malformed retrieval')
    items=[]
    seen_pages=set()
    for text,meta in zip(documents[0],metadata[0]):
        if not isinstance(text,str) or not isinstance(meta,dict) or meta.get('file_id')!=book['file_id']:continue
        page=meta.get('page_number')
        if type(page) is not int or not chapter['page_start']<=page<=chapter['page_end']:continue
        if meta.get('edition')!='pep-2022-standard-current':continue
        if page in seen_pages:continue
        seen_pages.add(page)
        printed_page=page-chapter['page_start']+chapter['printed_page']
        items.append({'text':text[:1400],'pdf_page':page,
                      'printed_page':printed_page,
                      'content_title':page_title(book,chapter,printed_page,text),
                      'book_title':book['title'],'review_status':'reference_only',
                      'page_image_path':f"/api/v1/textbooks/{book['id']}/pages/{printed_page}/image"})
        if len(items)>=4:break
    items.sort(key=lambda item: item['printed_page'])
    return {'book_id':book['id'],'chapter_id':chapter['id'],'items':items,
            'notice':'相关页已按页码排列，点标题展开原页。仅供阅读，未经题目审核，不作为标准答案。'}
