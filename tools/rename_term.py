#!/usr/bin/env python3
"""고유명사 표기를 통일한다. 이름을 바꾸면서 뒤따르는 조사도 받침에 맞춰 고친다.

번역 전에 용어집을 확정하지 않아서 같은 이름이 여러 표기로 갈렸다.

  アーシェス  -> 아셰스 291곳 / 아르셰스 122곳
  イオナサル  -> 이오나사르 669곳 / 이온살 11곳

표기만 바꾸면 조사가 어긋난다. 이온살(ㄹ받침) -> 이오나사르(받침 없음) 이므로
`이온살은` 은 `이오나사르는` 이 되어야 하고 `이온살이라면` 은 `이오나사르라면` 이
되어야 한다. 아셰스/아르셰스는 둘 다 받침이 없어 조사가 그대로다.

바꾼 뒤에는 반드시 scan_standin_collisions 를 다시 돌려라. 새 한글 음절이 생기면
폰트 대체 셀이 추가로 징발되어 전에는 멀쩡하던 곳이 새로 깨질 수 있다.
"""

import argparse
import csv
import html
import json
import re
from collections import Counter
from pathlib import Path

from source_honorifics import normalize_source_terms

REPO = Path(__file__).resolve().parents[1]
RECORD_HEADER = 32
ATTR = re.compile(r'(?P<head>\s[\w:.-]+\s*=\s*)(?P<q>["\'])(?P<value>.*?)(?P=q)', re.DOTALL)

# (바꿀 표기, 확정 표기)
# 2026-09-12부터 고유명사 음역은 사용자가 지정한 나무위키 Ar nosurge 계열
# 문서의 실제 표기를 우선한다. 문서에서 확인되지 않은 세부 아이템명은 빈도만으로
# 임의 확정하지 않는다. `想観→소칸` 같은 엔진 충돌 회피용 기술적 예외는 별도 규칙이다.
RENAMES = [
    ("아르셰스", "아셰스"),
    ("이온살", "이오나사르"),
    ("이오나살", "이오나사르"),
    ("페리온", "펠리온"),
    ("타트리아", "타토리아"),
    ("쿠온타브", "퀀타브"),
    ("퀀터브", "퀀타브"),
    ("콴타브", "퀀타브"),
    ("셸노트론", "셰르노트론"),
    ("쉘노트론", "셰르노트론"),
    ("세르노트론", "셰르노트론"),
    ("셸 노트론", "셰르노트론"),
    ("쉘 노트론", "셰르노트론"),
    ("각신락", "토키카구라"),
    ("극신락", "토키카구라"),
    ("코쿠신라쿠", "토키카구라"),
    ("코쿠신락", "토키카구라"),
    ("코쿠신가쿠", "토키카구라"),
    ("코쿠라쿠", "토키카구라"),
    ("천통공주", "텐토우키"),
    ("천통희", "텐토우키"),
    ("천통공", "텐토우키"),
    ("천통기", "텐토우키"),
    ("텐토히메", "텐토우키"),
    ("덴료사라", "텐료사라"),
    ("천령사라", "텐료사라"),
    ("천령 사라", "텐료사라"),
    ("천령사", "텐료사라"),
    ("텐료 사라", "텐료사라"),
    ("인터디메드", "인터디멘드"),
    ("인터디메이드", "인터디멘드"),
    ("인터디메인드", "인터디멘드"),
    ("인터디메인", "인터디멘드"),
    ("인터디맨드", "인터디멘드"),
    # 복합 표기를 먼저 처리해서 `별읽기대(호시요미다이)`가 중복 변환되지 않게 한다.
    ("별읽기대(호시요미다이)", "성영대"),
    ("성점대", "성영대"),
    ("호시요미다이", "성영대"),
    ("별읽기대", "성영대"),
    ("알노사쥬 관", "아르노사쥬관"),
    ("알노사쥬관", "아르노사쥬관"),
    ("알노사지 관", "아르노사쥬관"),
    ("아르 노사쥬 관", "아르노사쥬관"),
    ("아르노사쥬 관", "아르노사쥬관"),
    ("레날르", "레나루루"),
    ("레날루", "레나루루"),
    ("소레이르", "소레일"),
    ("솔레이르", "소레일"),
    ("휨노스", "휴므노스"),
    ("휴무노스", "휴므노스"),
    ("휴무네스피아", "휴므네스피어"),
    ("휴므네스피아", "휴므네스피어"),
    ("휴무네스피어", "휴므네스피어"),
    ("휴무네스", "휴므네스"),
    ("만슈사라", "만쥬사라"),
    ("만수사라", "만쥬사라"),
    ("만슈라", "만쥬사라"),
    ("만수구", "만쥬구"),
    ("휴무니스피어", "휴므네스피어"),
    ("흄네스피어", "휴므네스피어"),
    ("흄네스피아", "휴므네스피어"),
    ("휴무스피어", "휴므네스피어"),
    ("이그짓", "이그지트"),
    ("엑시트", "이그지트"),
    ("코론", "콜론"),
    ("코롱", "콜론"),
    ("홀스", "호루스"),
    ("호르스", "호루스"),
    ("휴무노포트", "휴므노포트"),
    ("휨노포르트", "휴므노포트"),
    ("베제리에르 파자", "베제리엘 파자"),
    ("베제리에르파자", "베제리엘 파자"),
    ("베제리엘 퍼지", "베제리엘 파자"),
    ("알 셸노", "아르 시엘노"),
    ("아르 시엘쨩", "아르 시엘노쨩"),
    ("보티명왕", "보리명왕"),
    ("샤를로드", "샤르 로드"),
    ("샤르로드", "샤르 로드"),
    ("사이런트 그린", "사일런트 그린"),
    ("펠체 쿨러", "펠티어 쿨러"),
    ("인피니티 글래스", "인피니티 글라스"),
    ("리셋 스톤", "리세타 스톤"),
    ("리세트 스톤", "리세타 스톤"),
    ("얽혀있는 소자", "엔탱글 소자"),
    ("얽힌 엔탱글 소자", "엔탱글 소자"),
    ("ＩＡＱＬ 이온 우산", "IAQL 전리 우산"),
    ("ＩＡＱＬ 전리 우산", "IAQL 전리 우산"),
    ("일격필살 파페", "일격필살 파르페"),
    ("펠티에 쿨러", "펠티어 쿨러"),
    ("브라이달 런치", "브라이덜 론치"),
    ("브라이덜 런치", "브라이덜 론치"),
    ("헬리카류전", "헬리컬루전"),
    ("헤리칼리전", "헬리컬루전"),
    ("헤리칼류전", "헬리컬루전"),
    ("헬리 퓨전", "헬리컬루전"),
    ("제노뮤 만두", "제노뮤 만쥬"),
    ("메자르 RNA", "메저 RNA"),
    ("메이저 RNA", "메저 RNA"),
    ("메주르 에누에이", "메저 RNA"),
    ("메저 ＲＮＡ", "메저 RNA"),
    ("포클리 슈에트", "포쿠리 스웨트"),
    ("포크리스 에트", "포쿠리 스웨트"),
    ("정지궤도 사출 장치", "정지 위성 궤도 사출 장치"),
    ("정지 궤도 위성 발사 장치", "정지 위성 궤도 사출 장치"),
    ("덴료사라중앙역앞", "텐료사라중앙역앞"),
    ("천령사라 중앙역 앞", "텐료사라 중앙역 앞"),
    ("하늘…… 좋은 곳이네요.", "소라…… 좋은 곳이네요."),
    ("세르른", "셰룬"),
    ("쉘른", "셰룬"),
    ("셸른", "셰룬"),
    ("쉘노사쥬", "셰르노사쥬"),
    ("셸노사쥬", "셰르노사쥬"),
    ("세르노사쥬", "셰르노사쥬"),
    ("쉘 노사쥬", "셰르노사쥬"),
    ("지릴리움", "질리리움"),
    ("지리리움", "질리리움"),
    ("지리륨", "질리리움"),
    ("샤라노아", "샤라노이아"),
    # `샤라노이` 자체는 정식 표기 `샤라노이아`의 접두부라 전역 치환하면
    # 이미 정상인 `샤라노이아`까지 `샤라노이아아`가 된다. 실제 누락형만 잡는다.
    ("샤라노이라곤", "샤라노이아라곤"),
    ("샤라노이라", "샤라노이아라"),
    ("계약인상계시", "계반상계시"),
    ("궤반상계시", "계반상계시"),
    ("샤르 마스터", "마스터 샤르"),
    ("센터 오브 더 라셸라", "센터 오브 라셸라"),
    # 天領割符는 천령증표, 일반 割符는 증표. 한국어 '할부'와 무관하다.
    ("천령할부", "천령증표"),
    ("천령 와리후", "천령증표"),
    ("텐료 와리후", "천령증표"),
    ("샤르 할부_", "샤르 증표_"),
    ("할부(와리후)", "증표"),
    ("할부(쿠폰)", "증표"),
    ("할부표", "증표"),
    # 같은 권위본에서 정식 표기가 이미 확정된 합성어/아이템명의 오타·오음역.
    ("네레이라코스", "네레이그라코스"),
    ("컨트리 샤알", "컨트리 샤르"),
    ("프리무노트론", "프림 노트론"),
    ("페펜 어트마크", "페펜앳마크"),
    ("립 크림", "리플 크림"),
    # 조합 아이템명 오역/오타. 원문 고유명과 이벤트 대사에서 직접 확인한 표기를 사용한다.
    ("이오나 샌드위치", "이오나사브레"),
    ("이온 사브레", "이오나사브레"),
    ("이오나 사브레", "이오나사브레"),
    ("네이 유우키", "유키 네이"),
    ("유우키 네이", "유키 네이"),
    ("유키 네리코", "유키 네이"),
    ("유우키 네리", "유키 네이"),
    ("유키 네리", "유키 네이"),
    ("유키 네네", "유키 네이"),
    ("유키 네오", "유키 네이"),
    ("일격필살 퍼레이드", "일격필살 파르페"),
    ("크림 카소다", "크림 캐소드"),
    ("샴 고로케 소시", "샴 고로케 소자"),
    ("시치미 고춧가루 소시", "시치미 고춧가루 소자"),
    ("네코미미 군사", "네코미미 병장"),
    ("네코미미 하사", "네코미미 병장"),
    ("샤르 빈즈", "샤리 빈즈"),
    ("샤르리 빈즈", "샤리 빈즈"),
    ("샤를리 빈즈", "샤리 빈즈"),
    ("오징어 댄스 클래스", "이카스 댄스 클래스"),
    ("멋진 댄스 클래스", "이카스 댄스 클래스"),
    ("이카스댄스 클래스", "이카스 댄스 클래스"),
    ("고에몬 부락", "고에몬탕"),
    ("고에몬 부로", "고에몬탕"),
    ("고에몬부로", "고에몬탕"),
    ("네이 아르샹세", "네이 아 프랑세"),
    ("네이야 프랑세", "네이 아 프랑세"),
    ("네이 아 프랑스", "네이 아 프랑세"),
    ("네이 아프랑스", "네이 아 프랑세"),
    ("네이아 프랑스", "네이 아 프랑세"),
    ("네이 프랑스", "네이 아 프랑세"),
    ("네이 프랑세", "네이 아 프랑세"),
    ("기갑연희", "기갑염희"),
    ("야르피네・노아", "야르피네・노이아"),
    ("노아의 제단", "노이아의 제단"),
    ("타트리안ＺＺ", "타토리안 ＺＺ"),
    ("타트리안Ｚ", "타토리안 Ｚ"),
    ("타트리안 Ｚ", "타토리안 Ｚ"),
    ("타토리아인 Ｚ", "타토리안 Ｚ"),
    ("타토리아 ＺＺ", "타토리안 ＺＺ"),
    ("타토리아 Ｚ", "타토리안 Ｚ"),
    # シェルノトロン 파생명도 확정 어근 셰르노트론과 같은 표기를 유지한다.
    ("셸노트로니카", "셰르노트로니카"),
    ("쉘노트로니카", "셰르노트로니카"),
    ("쉘 노트로니카", "셰르노트로니카"),
    ("세르노트로니카", "셰르노트로니카"),
    ("하모닉스 향", "하모니안 향"),
    ("ＤＩＹ", "DIY"),
    ("슈레리아역", "사비리역"),
    ("슈레리아 상가", "사비리 상점가"),
    ("슈레리아<CR>상가", "사비리<CR>상점가"),
    ("구라구라 글라세", "흔들흔들 글라세"),
    ("후루츠 폰타", "후르츠 폰타"),
    ("철인 가면 초변신", "철인 가면 초변화"),
    ("프리무노트론", "프림 노트론"),
    ("사오리 마을", "샤르촌"),
    ("사와 마을", "샤르촌"),
    ("사야촌", "샤르촌"),
    ("사유성", "샤르성"),
    ("사오성", "샤르성"),
    ("사아죠", "샤르성"),
    ("사오죠", "샤르성"),
    ("쿠르트페이나", "쿠르트페나"),
    ("플락트렐 도서관", "플락트루 도서관"),
    ("브레인 시냅스", "브레인 시냅시스"),
    ("포교단", "포교대"),
    ("아르노사쥬 관 Ｌ.Ｅ.", "아르노사쥬 관 ＬＥ"),
    ("좀비 램 스킨", "좀비 람스킨"),
    ("엑토플라즈만", "엑토플라즈맨"),
    ("팬데모닝", "판데 모닝"),
    ("유가무도회", "유아무도회"),
    ("송웨", "손웨"),
    ("아르셰르 스피어", "아르시엘스피어"),
    ("아셰르 스피어", "아르시엘스피어"),
    ("알셰르 스피어", "아르시엘스피어"),
    ("알셰르스피어", "아르시엘스피어"),
    ("아셰스피어 반전", "아르시엘스피어 반전"),
    ("베제리에르 결정", "베제리엘 결정"),
    ("베제리에르 칫솔", "베제리엘 칫솔"),
    ("인터디메드", "인터디멘드"),
    # NamuWiki/작품 표기에서 확인되는 전투·시마법 명칭.
    ("아셰르 스피어", "아르시엘스피어"),
    ("알셰르 스피어", "아르시엘스피어"),
    ("알셰르스피어", "아르시엘스피어"),
    ("아셰스피어", "아르시엘스피어"),
    ("하모닉스 버스트", "하모 버스트"),
    ("하모닉 버스트", "하모 버스트"),
    ("하모버스트", "하모 버스트"),
    # `にゅろきー`는 나무위키 표기 `뉴로키`. `ニュロキラー`는 별개의 고유명사이므로
    # `뉴로킬러` 자체를 전역 치환하지 않고, 실제로 にゅろきー를 잘못 음역한 변형만 정리한다.
    ("뉘로키", "뉴로키"),
    ("뇨로키", "뉴로키"),
    ("녀로키", "뉴로키"),
    ("녀루키", "뉴로키"),
    ("냐루키", "뉴로키"),
    ("쿠르트 힌멜", "쿠르트힘멜"),
    ("녀르키", "뉴로키"),
    ("뇨키", "뉴로키"),
    # 발화 장음 `ー`를 ASCII `-`로 옮긴 옛 번역 흔적. 아래는 원문과
    # 대응이 확실한 감탄/의성어/고유 애칭만 좁게 복구한다.
    ("에에-", "에에ー"),
    ("오오-", "오오ー"),
    ("햐하-", "햐하ー"),
    ("콰아아-", "콰아아ー"),
    ("우-군", "우ー군"),
    ("우승했다아-", "우승했다아ー"),
    ("삐-", "삐ー"),
    ("후아-", "후아ー"),
    ("어서 와--", "어서 와ー"),
    ("이-샨티", "이ー샨티"),
    ("아-샤루피나즈-", "아ー샤루피나즈ー"),
    ("뉴-ＦＯ", "뉴ーＦＯ"),
    # lexical long vowels are written naturally in Korean; remove the old ASCII
    # hyphen and follow the authoritative spelling used elsewhere in the project.
    ("뉴로킬러-Ｚ", "뉴로킬러Ｚ"),
    ("우리지요-Ｚ", "우리죠Ｚ"),
    ("우리지요-！？", "우리죠！？"),
    ("쿠르트-<CR>페이나", "쿠르트・<CR>페나"),
    ("진성 츄-관", "진성 츄관"),
]

# 고정 길이 main 슬롯에서 정식 표기 자체가 들어가지 않는 항목만 최소 축약한다.
# 白鷹의 정식 표기는 시로타카지만 일부 원본 슬롯은 2칸(6바이트)뿐이라 풀네임이
# 물리적으로 불가능하다. 가능한 곳은 풀네임을 우선하고, 불가능한 슬롯만 `시로`로
# 줄여서 예전 오역 `백호/백학/백악`을 남기지 않는다.
MAIN_TRANSLATION_OVERRIDES = {
    # `미소기`(9바이트)가 물리적으로 들어가지 않는 Switch 고정 슬롯은
    # 프로젝트에서 승인한 2글자 대체어 `정화`를 유지한다. PC는 compact=False로
    # 정식 표기 `미소기`를 사용할 수 있으므로 이 예외를 적용하지 않는다.
    1217: "여기, 제노메트리카 결정입니다. <CR>정화하실 때는 압의 탕을 꼭 이용해 주세요.",
    2035: "정화처",
    2045: "정화 대화・캐스",
    2046: "정화 대화・이온",
    2189: "정화 포인트가 해금되었습니다",
    2192: "정화리플레이",
    2791: "캐스_정화",
    2792: "캐스_정화(샤르 의상)",
    2794: "이온_정화１",
    2795: "이온_정화２",
    2797: "델타_정화１",
    2802: "카논_정화",
    3226: "캐스_정화정신세계용",
    3227: "캐스_정화(샤르 의상) 정신세계용",
    3229: "이온_정화１정신세계용",
    3230: "이온_정화２정신세계용",
    3233: "살리_정화",
    3234: "슈레리아_정화",
    3900: "정화",
    3996: "레레의 정화처",
    3997: "○레레의 정화처",
    5893: "<CLEG>２． 정화하기<CLNR><CR>제노메트리카 결정으로 캐릭터를 강화합니다． 세상 이야기를 진행하면 결정을 흡수할수있는곳도늘어납니다．",
    729: "시로타카",
    783: "시로타카자기만화좋아해？",
    784: "시로타카 자기 캐릭터에 설레？",
    960: "6:시로타카",
    1709: "토키×텐토우키：발동",
    1729: "토키×텐토우키：보조공격",
    1749: "토키×텐토우키：소발동",
    2113: "정신・시로타카",
    # Switch 고정 슬롯 전용 축약. PC는 relocation을 지원하므로 반드시
    # compact=False 경로에서 정식 표기(시로타카/텐토우키)를 사용한다.
    2648: "시로",
    2653: "텐토키",
    2814: "토키×텐토우키",
    3341: "시로타카1",
    3342: "시로타카2",
    3592: "시마법：토키ｘ텐토우키",
    5534: (
        "살리가 과거의 레시피를 바탕으로 제작한 이온 우산. 적의 공격을 무효화하는 "
        "기능이 있으며, 과거 천문이 사용했었다. 과거의 후회는 잠시 접어두고, "
        "시로타카에게 이것을 들려주고 싶다는 살리의 염원이 담겨 있다."
    ),
    # PC는 relocation으로 정식 제목 `전투의 기본`을 쓰고, Switch의 15바이트
    # 고정 슬롯만 조사 하나를 줄인 `전투 기본`을 사용한다.
    5766: "전투 기본",
    6451: "시로책",
    6457: "토키ｘ텐토우키",
}

# PC에서도 원문 문자열을 직접 참조해 relocation할 포인터 xref가 없는 고정 슬롯은
# 정식 표기 `미소기`를 넣을 수 없다. 이 둘은 플랫폼 공통으로 승인된 `정화` 축약을 유지한다.
MAIN_TRANSLATION_ALWAYS_OVERRIDES = {
    2189: "정화 포인트가 해금되었습니다",
    2192: "정화리플레이",
}

# 앞말에 받침이 없을 때 쓰는 형태. 긴 것부터 봐야 `이라면` 이 `이` 에 잡아먹히지 않는다.
NO_BATCHIM_FORMS = [
    ("이라면", "라면"), ("이라고", "라고"), ("이라는", "라는"), ("이라도", "라도"),
    ("이란", "란"), ("이랑", "랑"), ("이야", "야"), ("이여", "여"),
    ("으로", "로"), ("은", "는"), ("이", "가"), ("을", "를"), ("과", "와"),
]
BATCHIM_FORMS = {b: a for a, b in NO_BATCHIM_FORMS}


def has_batchim(char):
    if not ("가" <= char <= "힣"):
        return False
    return (ord(char) - 0xAC00) % 28 != 0


def rename(text):
    """이름/기호를 정규화하고, 받침이 달라지면 뒤따르는 조사도 맞춘다."""
    # 모든 텍스트 경로에서 강제 개행 직후의 레이아웃용 공백은 제거한다.
    # 이 공백이 남으면 대사 이외의 설명/UI/main 문자열도 새 줄 첫 글자가
    # 한 칸 들여써져 보인다. 공백 제거는 문자열을 짧게만 하므로 고정 슬롯에도 안전하다.
    text = re.sub(r"(<CR>)[ \u3000]+", r"\1", text)
    # 옛 자동 교정에서 발화 장음 `ー`가 문장부호 뒤로 밀린 흔적
    # (예: `좋아.ー`, `안녕.ー`)을 복구한다. 문장부호 자체는 보존하고
    # 장음만 실제 발음이 붙는 단어 뒤로 되돌린다.
    text = re.sub(r"([.!?。！？…]+)ー", r"ー\1", text)
    for before, after in RENAMES:
        if before not in text:
            continue
        was = has_batchim(before[-1])
        now = has_batchim(after[-1])
        if was == now:
            text = text.replace(before, after)
            continue
        # 받침 유무가 바뀌었다. 이름 바로 뒤에 오는 조사를 함께 본다.
        forms = NO_BATCHIM_FORMS if not now else [(b, a) for a, b in NO_BATCHIM_FORMS]
        pieces = text.split(before)
        rebuilt = [pieces[0]]
        for tail in pieces[1:]:
            for source, target in forms:
                if tail.startswith(source):
                    tail = target + tail[len(source):]
                    break
            rebuilt.append(tail)
        text = after.join(rebuilt)
    return text


def normalize_main_translation(index, text, japanese="", *, compact=True):
    """main 문자열의 소스 기반 용어를 통일한다.

    Switch NSO의 고정 슬롯 패치는 긴 정식 표기가 물리적으로 들어가지 않는 몇몇
    항목만 ``MAIN_TRANSLATION_OVERRIDES``로 축약한다. PC판은 문자열 relocation을
    지원하므로 ``compact=False``로 호출해 정식 표기를 그대로 유지한다.
    """
    # Legacy aliases must become their canonical base names before source-driven
    # honorific repair (e.g. 天統姫さま + 천통희씨 -> 텐토우키님).
    normalized = rename(text)
    if japanese:
        normalized = normalize_source_terms(japanese, normalized)
    index = int(index)
    if index in MAIN_TRANSLATION_ALWAYS_OVERRIDES:
        return MAIN_TRANSLATION_ALWAYS_OVERRIDES[index]
    if compact:
        return MAIN_TRANSLATION_OVERRIDES.get(index, normalized)
    return normalized


def parse_ebm(data):
    count = int.from_bytes(data[:4], "little")
    position, records = 4, []
    for _ in range(count):
        header = data[position:position + RECORD_HEADER]
        length = int.from_bytes(data[position + RECORD_HEADER:position + RECORD_HEADER + 4], "little")
        start = position + RECORD_HEADER + 4
        end = start + length
        records.append([header, data[start:end - 1].decode("utf-8")])
        position = end
    return records


def build_ebm(records):
    out = bytearray(len(records).to_bytes(4, "little"))
    for header, text in records:
        payload = text.encode("utf-8") + bytes(1)
        out += header + len(payload).to_bytes(4, "little") + payload
    return bytes(out)


def main():
    csv.field_size_limit(1 << 30)
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    mapping = json.loads((REPO / "build" / "final_mod_report.json")
                         .read_text(encoding="utf-8"))["hangul_to_standin"]

    def byte_length(text):
        return len("".join(mapping.get(c, c) for c in text).encode("utf-8"))

    totals = Counter()
    edits = {}

    # --- main 실행 파일 문자열 --------------------------------------------
    path = REPO / "translations" / "exefs" / "main_1.0.1.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    for row in rows:
        if not row["translation"]:
            continue
        new = rename(row["translation"])
        if new == row["translation"]:
            continue
        if byte_length(new) > int(row["capacity_bytes"]):
            print(f"  용량 초과로 건너뜀 [main {row['index']}] {new[:60]}")
            totals["skipped"] += 1
            continue
        print(f"  [main {row['index']}] {row['translation'][:70]!r}")
        print(f"        -> {new[:70]!r}")
        edits[row["translation"]] = new
        row["translation"] = new
        totals["main"] += 1
    if totals["main"] and not args.dry_run:
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    # --- 이벤트 대사 EBM --------------------------------------------------
    for translated in sorted((REPO / "translations" / "romfs" / "Event" / "event").rglob("*.ebm")):
        records = parse_ebm(translated.read_bytes())
        dirty = False
        for index, row in enumerate(records):
            new = rename(row[1])
            if new == row[1]:
                continue
            print(f"  [{translated.name}[{index}]] {row[1][:70]!r}")
            print(f"        -> {new[:70]!r}")
            edits[row[1]] = new
            row[1] = new
            dirty = True
            totals["ebm"] += 1
        if dirty and not args.dry_run:
            translated.write_bytes(build_ebm(records))

    # --- Saves XML --------------------------------------------------------
    for translated in sorted((REPO / "translations" / "romfs" / "Saves").rglob("*.xml")):
        text = translated.read_text(encoding="utf-8", newline="")
        state = {"hits": 0}

        def replace(match):
            value = html.unescape(match.group("value"))
            new = rename(value)
            if new == value:
                return match.group(0)
            state["hits"] += 1
            print(f"  [{translated.name}] {value[:70]!r}")
            print(f"        -> {new[:70]!r}")
            edits[value] = new
            quote = match.group("q")
            escaped = (new.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                       .replace(quote, "&quot;" if quote == '"' else "&apos;"))
            return match.group("head") + quote + escaped + quote

        updated = ATTR.sub(replace, text)
        if state["hits"] and not args.dry_run:
            translated.write_text(updated, encoding="utf-8", newline="")
        totals["saves"] += state["hits"]

    # --- 대화 선택지 ------------------------------------------------------
    balloon = REPO / "translations" / "romfs" / "Event" / "balloonsel" / "balloonseldata.json"
    if balloon.is_file():
        groups = json.loads(balloon.read_text(encoding="utf-8"))
        changed = 0
        for group in groups:
            for position, option in enumerate(group):
                new = rename(option)
                if new != option:
                    print(f"  [balloonsel] {option[:70]!r}")
                    print(f"        -> {new[:70]!r}")
                    edits[option] = new
                    group[position] = new
                    changed += 1
        if changed and not args.dry_run:
            balloon.write_text(json.dumps(groups, ensure_ascii=False, indent=1),
                               encoding="utf-8")
        totals["balloonsel"] = changed

    # --- 번역 캐시 --------------------------------------------------------
    for name in ("saves_translation_cache.json", "main_1.0.1_translation_cache.json",
                 "balloonsel_translation_cache.json", "three_line_shortening_cache.json",
                 "main_expand_cache.json"):
        cache_path = REPO / "build" / name
        if not cache_path.is_file():
            continue
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(cache, dict):
            continue
        changed = 0
        for key, value in list(cache.items()):
            if not isinstance(value, str):
                continue
            new = rename(value)
            if new != value:
                cache[key] = new
                changed += 1
        if changed:
            print(f"  캐시 {name}: {changed}건")
            totals["cache"] += changed
            if not args.dry_run:
                cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1),
                                      encoding="utf-8")

    print("\n" + "  ".join(f"{k} {v}" for k, v in totals.items()))
    if args.dry_run:
        print("(dry-run: 파일을 쓰지 않았습니다)")


if __name__ == "__main__":
    main()
