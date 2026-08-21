# 아르노사쥬/아르노서지 DX 한국어 번역 패치

> 🙏 이 패치는 **AI 번역 기반이라 발생할 수 있는 오역이나 어색한 표현을 크게 개의치 않고 플레이하실 수 있는 분들을 위한 비공식 팬 패치**입니다.

> ⚠️ **완전 한글화 패치가 아닙니다.** 이벤트 대사 대부분은 번역되어 있지만, 대사 EBM과 별도로 관리되는 화자명·메뉴·그래픽 문구 등은 일본어로 남아 있을 수 있습니다.
>
> ⚠️ 화자 정보가 원문 텍스트만으로 명확하지 않은 장면은 같은 인물의 존댓말/반말이나 말투가 일관되지 않을 수 있습니다.

Nintendo Switch판 『Ar nosurge: Ode to an Unborn Star DX』(アルノサージュ ～生まれいずる星へ祈る詩～ DX)의 비공식 한국어 번역 패치입니다.

- 이벤트 대사 파일 2,239개를 번역합니다.
- 시스템 메시지·메뉴·상점 등 Saves XML 135개를 번역합니다.
- 아이템명·업적·미소기 대화 등 스크램블된 `Saves/*.xml.e` 25개를 번역합니다.
- 대화 선택지 1,790개(`balloonseldata.bsb`)를 번역합니다.
- 업데이트 1.0.1 `main` 실행 파일에서 추출한 일본어 문자열 6,665개를 번역합니다.
- 메뉴·시스템 화면의 UI 텍스처 4개(`common`/`mainmenu`/`system`/`window`)를 번역합니다.
- 고유 한글 음절 1,427자를 게임 내장 폰트 아틀라스에 매핑했습니다.
- 원본 NSP/XCI를 수정하지 않고 Atmosphère/Ryujinx의 LayeredFS 모드로 적용합니다.
- 폰트 매핑 추출, 번역문 치환, 폰트 생성 과정을 Python 소스로 공개합니다.

### 알려진 제약

패치 성격상 고치기 어렵거나 고치지 않은 부분이 있습니다. 설치 전에 확인해 주세요.

**1. 동영상과 일부 이미지는 번역되지 않았습니다**

오프닝·엔딩 등 **동영상에 들어간 자막과 문구는 그대로 일본어**입니다. 영상 자체를
다시 만들어야 해서 이 패치의 범위를 벗어납니다.

이미지(텍스처)에 그려진 일본어도 일부만 번역했습니다. 메뉴·시스템 화면
(`common` / `mainmenu` / `system` / `window`)은 직접 편집해 한국어로 바꿨지만,
튜토리얼 이미지 53장과 바이오스 설명 22장, 타이틀 화면, 맵 이동 화면 등은
일본어로 남아 있습니다. 자세한 목록은 아래 "아직 번역되지 않았거나 확인이 필요한 부분"에 있습니다.

**2. 설명창(텍스트 박스)을 넘치는 문장이 있습니다**

아이템·용어집 설명처럼 **글상자 크기가 정해진 화면에서 한국어가 상자를 넘쳐
잘려 보이는 곳이 있습니다.** 상자 크기와 줄바꿈 폭이 게임 실행 파일에 박혀 있어
번역문 쪽에서는 손쓸 방법이 마땅치 않습니다.

게임은 대사창을 **20자에서 강제로 줄바꿈**하는데, 이때 폭이 아니라 글자 수로 셉니다.
그래서 공백이 많은 줄은 오른쪽이 비어 보이고, 반대로 내용이 길면 3줄짜리 창을 넘겨
뒷부분이 안 보입니다. 번역문에서 줄바꿈을 정리해 최대한 맞췄지만 완전히 없애지는
못했습니다.

**3. 실행 파일 안 문장은 일부 간소화되어 있습니다**

메뉴명·지명·아이템 설명 일부는 `main` 실행 파일 안에 **크기가 고정된 자리**로 들어
있습니다. 뒤에 다른 데이터가 바로 붙어 있어 한 바이트라도 넘기면 게임이 멈추기
때문에, 자리에 맞추려고 띄어쓰기를 빼거나 표현을 줄인 곳이 있습니다.

번역 6,665개 중 **674개가 이런 이유로 축약된 상태**이며(그중 541개는 남는 자리가
2바이트 이하), 긴 문장인데 띄어쓰기가 전혀 없는 것이 177개입니다. `시마법:아메노신권`,
`린마선스기노역`처럼 붙어 나오는 표기가 여기에 해당합니다. **번역 누락이 아니라
의도적인 제약**입니다. (자리가 남는데도 과하게 줄어 있던 106개는 자연스러운 문장으로
되돌렸습니다.)

같은 이유로 `！ ？ （）` 같은 전각 부호를 원문대로 되살리지 못하고 반각으로 둔 곳이
150군데 있습니다.

> 💬 오역, 미번역 문구, 깨진 글자나 버그를 발견하시면 [Issues 탭](../../issues)에 장면·대사·스크린샷을 함께 제보해 주세요.

### 프로젝트 담당

| 역할 | 담당 |
|---|---|
| 프로젝트 관리·실기 확인 | TAMTAMQ |
| 번역 | gemma-4-26b-a4b-it-qat |
| 번역 검수 | qwen3.8-27b, TAMTAMQ |
| 초기 폰트 조사 | Claude Code |
| 폰트 UV 분석·패치 구현 | OpenAI Codex, TAMTAMQ |

## 1. 원본 확인

패치 대상은 일본판 Nintendo Switch용 『Ar nosurge DX』입니다.

| 항목 | 값 |
|---|---|
| 기본 Title ID | `01003CF0128DE000` |
| 업데이트 Title ID | `01003CF0128DE800` |
| 지원 게임 버전 | 기본 버전 및 업데이트 `1.0.1` |
| 모드 적용 경로 | 기본 Title ID인 `01003CF0128DE000` 사용 |

이 패치는 **업데이트 1.0.1이 설치된 게임에 적용됩니다.** 업데이트를 설치한 경우에도 패치 폴더는 업데이트 Title ID가 아니라 기본 Title ID인 `01003CF0128DE000` 아래에 배치해야 합니다.

다른 지역판이나 다른 게임에는 적용하지 마세요. 정당하게 소유한 정품 게임에서만 개인적으로 사용해 주세요. 게임 원본 NSP/XCI, 키, 펌웨어는 이 저장소에 포함되어 있지 않습니다.

## 2. 패치 적용

### 2-1. Atmosphère

1. 저장소 또는 [Releases](../../releases)에서 패치를 받습니다.
2. `atmosphere` 폴더를 SD 카드 최상위에 복사합니다.
3. 최종 경로가 아래와 같은지 확인합니다.

```text
atmosphere/contents/01003CF0128DE000/romfs/Event/event/...
atmosphere/contents/01003CF0128DE000/romfs/Data/NX/Font/MainFont_nx_0.g1t
atmosphere/contents/01003CF0128DE000/romfs/Saves/systemMessage/...
atmosphere/exefs_patches/ArNosurgeKoreanUI/28F3C3965CEB60AC18A23E2B2C0C4BEEE3C81D8B.ips
atmosphere/exefs_patches/ArNosurgeFpsUnlock/28F3C3965CEB60AC18A23E2B2C0C4BEEE3C81D8B.ips  # 선택
```

### 2-2. Ryujinx

1. 게임 목록에서 아르노사쥬/아르노서지를 우클릭하고 모드 폴더를 엽니다.
2. `korean_final` 같은 임의의 폴더를 하나 만듭니다.
3. 그 안에 저장소의 `atmosphere/contents/01003CF0128DE000/romfs` 폴더를 복사합니다.
4. `atmosphere/exefs_patches/ArNosurgeKoreanUI/28F3C3965CEB60AC18A23E2B2C0C4BEEE3C81D8B.ips`를 `korean_final/exefs/` 아래에 복사합니다.

```text
mods/contents/01003cf0128de000/korean_final/romfs/...
mods/contents/01003cf0128de000/korean_final/exefs/28F3C3965CEB60AC18A23E2B2C0C4BEEE3C81D8B.ips
```

기존 대사·폰트 시험 모드가 함께 활성화되어 있으면 충돌할 수 있으므로 다른 모드는 비활성화해 주세요.

### 2-3. 60FPS 프레임 제한 해제 (선택)

원래 30FPS로 고정된 프레임 제한을 해제합니다. 한국어 패치와 **독립된 별도 패치**이므로
원하지 않으면 넣지 않아도 되고, 넣은 뒤 마음에 들지 않으면 해당 폴더만 지우면 됩니다.

Atmosphère는 `atmosphere` 폴더를 SD 카드에 복사할 때 함께 적용됩니다.

Ryujinx에서는 한국어 패치와 **별개의 모드 폴더**로 만듭니다.

1. 모드 폴더에 `fps_unlock` 같은 임의의 폴더를 하나 더 만듭니다.
2. 그 안 `exefs/`에 `atmosphere/exefs_patches/ArNosurgeFpsUnlock/`의 IPS를 복사합니다.

```text
mods/contents/01003cf0128de000/korean_final/...   # 한국어 패치
mods/contents/01003cf0128de000/fps_unlock/exefs/28F3C3965CEB60AC18A23E2B2C0C4BEEE3C81D8B.ips
```

동작 방식은 다음과 같습니다. 게임은 프레임 대기 값을 레지스터로 넘겨 호출하는데,

```text
0x3D07CC   mov  w1, w21     ; 대기 프레임 수
0x3D07D0   blr  x8          ; 프레임 대기 호출
```

이 중 `mov w1, w21` 을 `mov w1, wzr`(0) 로 바꿔 대기를 없앱니다. 실제 변경은 **1바이트**이며
IPS 파일 전체가 14바이트입니다.

이 패치는 빌드 ID로 대상을 확인하므로 게임 버전이 다르면 자동으로 무시됩니다. 따라서
버전이 맞지 않아도 게임이 손상되거나 튕기지 않습니다.

> 프레임 해제는 게임 속도·물리·연출이 30FPS 기준으로 맞춰진 부분에 영향을 줄 수 있습니다.
> 이상이 느껴지면 `fps_unlock` 폴더만 제거하세요.

## 3. 패치 내용

| 영역 | 수량 | 상태 |
|---|---:|---|
| 이벤트 대사 EBM | 2,239개 | 한국어 번역 및 한자 대체 코드 적용 |
| Saves XML (시스템 메시지·UI) | 135개 | 한국어 번역 및 한자 대체 코드 적용 |
| Saves `*.xml.e` (아이템·업적·미소기·SNS) | 25개 | 버전 1 스크램블 해독 후 번역·재인코딩 |
| 대화 선택지 `balloonseldata.bsb` | 1,790개 | 한국어 번역, 구조 바이트 단위 검증 |
| 이벤트 스크립트 `SYS:MESS` | 6개 파일 | 원문과 같은 바이트 길이로 치환 |
| UI 텍스처 `.g1t` | 4개 | 직접 편집한 한국어 텍스처 적용 |
| 업데이트 1.0.1 `main` 문자열 | 6,665개 | 고정 길이 IPS 번역, 길이 초과 0건 |
| 고유 한글 음절 | 1,427자 | 게임 폰트 아틀라스에 추가 |
| 한글 출현 수 | 975,070회 | 전부 대체 코드로 변환 |
| 메인 폰트 | 1개 | `MainFont_nx_0.g1t` 알파 블록 수정 |
| EBM 구조 검증 | 2,239개 | 오류 0건 |
| 역변환 검증 | 2,239개 | 원 번역본과 불일치 0건 |

### `main` 문자열의 띄어쓰기 제거와 축약

메뉴명·지명·인명·내부 안내 문구 중 일부는 EBM이나 XML이 아니라 업데이트 1.0.1의 `main` 실행 파일 안에 NUL 종료 UTF-8 문자열로 들어 있습니다. 이 문자열은 원문 바로 뒤에 다른 문자열이나 데이터가 이어지는 **고정 크기 슬롯**이므로, 번역문이 원문 공간보다 길면 다음 데이터를 침범해 게임이 멈추거나 종료될 수 있습니다.

한국어와 일본어의 완성형 문자는 UTF-8에서 대체로 3바이트지만 한국어 번역에는 띄어쓰기와 조사가 추가됩니다. 이 때문에 의미상 더 짧아 보이는 한국어도 원래 슬롯을 몇 바이트 초과할 수 있습니다. `main` 번역은 다음 순서로 슬롯 크기를 맞췄습니다.

1. 자연스러운 번역문을 먼저 작성합니다.
2. 슬롯을 초과한 문장은 띄어쓰기를 제거합니다.
3. 그래도 초과하면 조사·주어·종결어미를 생략하고 짧은 동의어를 사용합니다.
4. 지명·인명·기술명은 식별 가능한 범위에서 줄이고, 내부 식별자는 짧은 표기로 바꿉니다.
5. 단어 중간을 바이트 단위로 자르지 않으며, `<CR>`, `<IMxx>` 같은 제어문자는 원문 개수와 순서를 유지합니다.

따라서 일부 `main` 문구는 일반적인 한국어 표기와 달리 띄어쓰기가 없거나 `시마법:아메노신권`, `린마선스기노역`처럼 축약되어 표시됩니다. 이는 번역 누락이 아니라 **실행 파일의 인접 데이터 손상을 피하기 위한 의도적인 제약**입니다.

초기 조사에서는 긴 번역문을 별도의 빈 영역에 넣고 포인터를 바꾸는 방식도 시험했습니다. 포인터와 AArch64 참조 자체는 수정할 수 있었지만, 실행 파일의 0영역 일부가 실제 더미가 아니라 시스템 전환 시 사용하는 테이블이어서 시스템 메뉴에서 메인 메뉴로 돌아갈 때 게임이 멈췄습니다. 현재 배포본은 이 포인터 재배치 방식을 전혀 사용하지 않으며, 모든 `main` 번역문이 원래 슬롯 이내인지 빌드 시 검사합니다. 현재 결과는 **6,665개 적용, 길이 초과 0개, 제외 0개**입니다.

### 전각 문장부호 복원 (`restore_fullwidth_punctuation.py`)

번역 대상은 일본어뿐인데, 모델이 `！ ？ （） ～ ＆ ＋` 같은 **전각 문장부호까지
ASCII로 바꿔 놓았습니다.** 원래 일본어가 아니었던 문자를 조용히 고친 것이라
원본 유지 원칙에 어긋납니다. 규모는 다음과 같았습니다.

| 대상 | 복원 |
|---|---:|
| 이벤트 대사 EBM | 20,238 |
| Saves XML | 4,104 |
| `main` | 1,547 |
| 대화 선택지 | 637 |

복원은 단위(CSV 한 행 / EBM 한 레코드 / XML 속성 하나 / 선택지 하나)별로 판단합니다.
**원본이 그 전각 형태를 썼고 동시에 ASCII 형태를 쓰지 않은 경우에만** 되돌리므로,
원본이 둘을 섞어 쓴 자리는 손대지 않습니다.

EBM·Saves·선택지는 길이 접두사 방식이라 전부 복원됐습니다(잔여 위반 0).

`main`은 고정 슬롯이라 285행이 남았습니다. 전각 부호는 3바이트, ASCII는 1바이트여서
바꾸면 슬롯을 넘칩니다(부족분 중앙값 2바이트). 이 행들은 **띄어쓰기를 지우면 들어가지만,
읽기 편한 띄어쓰기를 남기는 쪽을 택해 ASCII 부호를 그대로 두었습니다.** 원본 유지보다
가독성을 우선한 의도적인 예외이며, 해당하는 곳은 285행뿐입니다.

### 과하게 줄어든 번역 되돌리기 (`expand_main_compaction.py`)

`compact_main_translations.py`는 슬롯을 넘긴 번역문의 띄어쓰기를 지우고 단어를
줄입니다. 그런데 이 단계가 최종 글리프 매핑이 확정되기 전에 돌아서, 실제보다
바이트를 크게 잡고 필요 이상으로 깎은 행이 많이 남았습니다. 예를 들어 6119행은
242바이트 슬롯에 168바이트만 쓰면서 전보문처럼 붙어 있었습니다.

압축 표시가 붙은 780행을 재측정한 결과는 다음과 같습니다.

| 구분 | 행 수 |
|---|---:|
| 여유 0바이트 — 압축이 실제로 필요했던 행 | 489 |
| 여유가 남은 행 — 불필요하게 줄인 행 | 291 |

`tools/expand_main_compaction.py`는 여유가 남은 행만 원문에서 다시 번역하되
바이트 예산을 함께 알려 주고, 아래 조건을 **모두** 통과할 때만 교체합니다.
하나라도 걸리면 기존 번역을 그대로 두므로 후퇴하지 않습니다.

- 슬롯 용량 이내
- `<CR>`·`<CLEG>` 등 제어 토큰의 개수와 순서 일치
- 원문의 「」 『』 개수 일치 (따옴표로 바꾸는 것 금지)
- 원문에 존칭이 없으면 씨/님/짱/군을 새로 붙이지 않음
- 고유명사가 저장소의 확정 표기와 일치 (`ジェノミライ`→제노미라이 등)
- 공백을 뺀 실질 내용이 기존보다 5% 넘게 줄지 않음
- 띄어쓰기가 기존보다 줄지 않음

모델이 예산을 넘기면 실제 바이트 수를 되먹여 다시 줄이게 하고, 그래도 넘치면
오른쪽부터 공백을 하나씩 지워 슬롯이 감당하는 만큼의 띄어쓰기를 남깁니다.

### `.rodata`만 고쳐서는 안 되는 짧은 문자열 (`inline_tail_fix.py`)

`main`의 고정 슬롯을 번역문으로 덮어썼는데도 `아이템 도감`, `용어집`처럼 **짧은 메뉴 항목의 끝부분만**
빈 네모(두부 글자)로 표시되는 문제가 있었습니다. 원인은 폰트가 아니라 컴파일러 최적화입니다.

`std::string`을 짧은 리터럴로 만들 때 clang은 문자열 전체를 `.rodata`에서 복사하지 않습니다.
앞부분만 `ldr`(8바이트) 또는 `ldp`(16바이트)로 읽어오고, **남은 꼬리 바이트와 libc++ SSO 길이 필드
(`바이트길이 << 1`)는 MOV/MOVK 즉시값으로 `.text`에 직접 박아 넣습니다.**

```
mov  w8,  #0x18              ; SSO 길이 필드 = 12바이트 << 1
adrp x9,  #0x71d000
add  x9,  x9, #0x429         ; -> .rodata의 "人物図鑑"
ldr  x8,  [x9]               ; 앞 8바이트만 .rodata에서 복사
mov  w10, #0xe9b3            ; 나머지 4바이트는 여기에 상수로 박혀 있음
movk w10, #0x9191, lsl #16   ;   0x9191E9B3 -> B3 E9 91 91
```

따라서 `.rodata`만 패치하면 앞부분은 한글로 바뀌고 꼬리는 일본어 바이트가 그대로 남아, 둘이 섞인
바이트열이 폰트에 없는 코드포인트로 디코드되어 네모로 그려집니다. 번역문이 원문보다 짧을 때는
낡은 SSO 길이 필드 때문에 뒤쪽 잔여 바이트까지 함께 그려집니다.

`tools/inline_tail_fix.py`는 각 문자열 주소를 만드는 ADRP+ADD 쌍을 찾고, 그 주변 명령
(`-0x18`~`+0x48`) 에서 원문 꼬리 바이트·SSO 길이와 값이 일치하는 MOVZ/MOVK 즉시값을 찾아
번역문 기준으로 다시 씁니다. 현재 빌드에서 **57개 명령**이 이렇게 수정됩니다.

이 때문에 `translate_all.py`에는 원본 실행 파일 경로가 필요합니다.

```powershell
python translate_all.py --original-font <MainFont_nx_0.g1t> --original-main <원본 exefs\main> --original-balloonsel <원본 balloonseldata.bsb> --original-event <원본 romfs\Event> --original-ui-images <원본 romfs\Data\NX\ui>
```

`--original-main`을 생략하면 나머지는 정상 빌드되지만 짧은 메뉴 항목의 끝부분이 깨진 채로 남습니다.

### 이미지에 그려진 일본어 번역 (`translateImage/`)

메뉴·시스템 화면의 일본어 상당수는 텍스트가 아니라 텍스처에 그려져 있어 텍스트
패치로는 손댈 수 없습니다. 이 부분은 `.g1t` 텍스처를 직접 편집해서 넣습니다.

1. 정품에서 추출한 원본 `.g1t`를 이미지 편집 도구로 열어 일본어를 한국어로 고칩니다.
   자리를 그대로 두고 픽셀만 바꾸므로 **파일 크기가 원본과 같아야 합니다.**
2. 고친 `.g1t`를 저장소 루트의 `translateImage/`에 그대로 둡니다. 하위 폴더는 필요 없습니다.
3. `translate_all.py`가 7단계에서 `romfs/Data/NX/ui/`로 넣습니다.

```powershell
python translate_all.py ... --original-ui-images <언팩 romfs>\Data\NX\ui
```

`tools/build_ui_images.py`가 넣기 전에 G1T 매직(`GT1G`)과 원본 대비 크기를 확인합니다.
`--original-ui-images`를 주지 않으면 크기 검사는 건너뛰고 매직만 봅니다.

현재 `common.g1t`, `mainmenu.g1t`, `system.g1t`, `window.g1t` 네 개가 번역되어 있습니다.

> **`translateImage/`는 저장소에 포함되지 않습니다.**
> 이 폴더의 `.g1t`는 정품에서 추출한 텍스처를 직접 고친 것이라 저장소로 배포할 수 없고,
> 네 개 합계가 약 59MB(`mainmenu.g1t` 하나가 42MB)라 크기로도 맞지 않습니다.
> `.xcf` 같은 편집 도구 작업 파일도 두지 않습니다.
>
> 이미 번역된 결과물은 릴리스의 `atmosphere/contents/<Title ID>/romfs/Data/NX/ui/`에
> 들어 있으므로, 이어서 손보실 때는 그 파일을 `translateImage/`에 넣고 편집하시면 됩니다.
> 처음부터 하실 때는 본인 게임에서 추출한 원본 `.g1t`로 시작하세요.

### 원본 폰트는 반드시 게임에서 갓 추출한 것이어야 한다

`--original-font`에 **이미 한글로 패치된 폰트**를 넘기면 빌드는 성공하지만 게임에서
글자가 깨집니다. 패치는 원본 아틀라스의 특정 한자 셀만 골라 한글로 덮어쓰는 방식이라,
입력이 이미 패치된 폰트면 **예전 배정으로 그려진 한글이 그대로 남습니다.** 현재 배정이
"이 셀에는 아직 일본어가 있다"고 가정하는 자리에 엉뚱한 한글이 들어 있으므로,
메뉴 라벨·숫자(플레이 시간, 소지금, LV)·버튼 표시가 알 수 없는 음절로 나옵니다.

증상만 보면 매핑 충돌이나 폰트 생성 버그처럼 보이지만 원인은 입력 파일 하나입니다.
그래서 `build_final_korean_mod.py`가 원본 해시를 검증하고, 다르면 빌드를 중단합니다.

```
VERIFIED_ORIGINAL_SHA256 = 732f2aeb3860c76832dc18ae80de5a775addef561df41e2984d7ca2c64e810b4
```

해시가 다르면 추가로 "이미 패치된 폰트인가"를 구조적으로도 검사합니다(선택된 셀에
현재 배정대로 한글이 이미 그려져 있는지). 게임 버전이 달라 해시가 다른 것이 확실할
때만 `--allow-unverified-font`로 우회하세요.

### 이벤트 스크립트가 직접 띄우는 시스템 메시지 (`.ebd`)

`romfs/Event/**/*.ebd`는 이벤트 그래프 데이터입니다(2,748개). 안에 든 일본어
문자열 15만 개는 거의 전부 편집기용 라벨이라 화면에 나오지 않습니다 —
`説明`, `新規アクション`, `キャラ位置指定`, 그리고 EBM 대사를 그대로 딴
`SEL／1／<대사>` 분기 이름 등입니다.

예외가 하나 있습니다. **`SYS:MESS` 태그 바로 뒤의 문자열은 스크립트가 플레이어에게
직접 띄우는 메시지입니다.** 전체를 훑은 결과 해당하는 것은 한 종류뿐이었습니다.

```
現在この扉はロック中です。暗証番号を入力してください。
  -> 현재 이 문은 잠겨 있습니다. 비밀번호를 입력해 주세요.
```

`Event/event/C21_2/EVENT_C21_2_130~180.ebd` 6개 파일에 들어 있습니다.

문자열은 `u32 길이(NUL 포함) + CP932 바이트 + NUL` 형식입니다. `tools/build_event_sysmess.py`는
한글 대체 문자를 CP932로 인코딩해 **원문과 정확히 같은 바이트 길이로** 덮어씁니다
(짧으면 공백으로 채움). 길이 필드와 뒤따르는 모든 오프셋이 그대로 유지되므로
구조가 깨질 여지가 없습니다. 대체 문자는 전부 JIS 한자라 CP932로 인코딩됩니다.

`translate_all.py`의 6단계(`6/6`)로 연결되어 있으며 `--original-event`가 필요합니다.

### 대화 선택지 `balloonseldata.bsb`

`romfs/Event/balloonsel/balloonseldata.bsb`에는 대화 중 표시되는 **선택지 1,790개**
(`はい` / `いいえ` / `仲間にする` …)가 들어 있습니다. EBM도 XML도 아닌 독자 포맷이라
오랫동안 파이프라인에 잡히지 않았고, 그 결과 선택지가 일본어로 남아 있었습니다.

이게 단순한 미번역으로 끝나지 않는 이유가 있습니다. 한글 패치는 폰트 아틀라스에서
게임이 쓰지 않는 한자 셀을 골라 한글 글리프로 덮어쓰는 방식입니다. 번역되지 않은
일본어가 남아 있으면, 그 안의 한자가 마침 한글용으로 징발된 셀일 때 **엉뚱한 한글
한 글자로 그려집니다.** 실제로 이 파일 안에 그런 문자가 504자 있었습니다
(`座`→`멕`, `率`→`쉐`, `低`→`뽕` 등).

포맷은 단순한 길이 접두사 구조입니다.

```
u32          그룹 수
그룹마다:
    u32      선택지 수
    선택지마다:
        u32  NUL 포함 바이트 길이
        ...  UTF-8 본문 + NUL
```

각 선택지는 말풍선 여백용 전각 공백(U+3000)으로 끝나므로 번역기가 이를 그대로
복원합니다. `tools/balloonsel.py`가 읽기/쓰기를, `tools/translate_balloonsel.py`가
추출·번역을, `tools/build_balloonsel.py`가 대체 문자 치환 후 재작성을 담당합니다.
고정 슬롯이 아니라 길이 접두사 방식이므로 `main`과 달리 길이 제약이 없습니다.

```powershell
python tools\translate_balloonsel.py --source <원본 balloonseldata.bsb>
```

`translate_all.py`의 5단계(`5/5`)로 연결되어 있으며 `--original-balloonsel`이 필요합니다.
지정하지 않으면 선택지가 일본어로 남고 위와 같은 글자 깨짐이 다시 발생합니다.

### `Saves/*.xml.e` 게임 데이터 디코더

아이템명·업적·미소기(禊) 대화·SNS 패러디 대사 등 게임 데이터 상당수는 EBM·시스템 XML이 아니라
`romfs/Saves/` 아래 `.xml.e`로 암호화(스크램블+압축)된 XML 192개에 들어 있습니다. 이 포맷은
Koei Tecmo/Gust의 자체 포맷이며, 공개 도구인 [gust_tools](https://github.com/VitaSmith/gust_tools)의
`gust_enc`는 스크램블링 "버전 2·3"만 지원합니다. 이 게임은 버전 2·3보다 오래된 **버전 1**을 사용해서
공개 도구로는 열 수 없었고, gust_tools 관리자도 버전 1은 구현을 포기했다고 밝힌 상태였습니다.

`tools/decode_saves_xml_e.py`는 Switch용 `main` 실행 파일의 리소스 로더를 디스어셈블해서 알아낸
버전 1 전용 상수(`RANDOM_INCREMENT=0x2fa5`, 주 스크램블 상수 `0x3b9a728b` — gust_enc.c의 버전 2·3
상수 `0x2f09`/`0x3b9a73c9`와 상위 16비트만 같고 하위 16비트가 다릅니다)와, gust_tools가 이미
공개해 둔 "Ar nosurge Plus"(ANP) 시드 값을 조합해 버전 1 파일을 평문 XML로 복원합니다. 192개
파일 전부 체크섬 검증을 통과하고 정상적인 Shift-JIS XML로 풀립니다. 자세한 라이선스 관련 사항은
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)를 참고하세요.

```powershell
# 디코딩: .xml.e -> 평문 XML
python tools\decode_saves_xml_e.py <파일 또는 여러 파일.xml.e> --out-dir <출력 폴더>

# 인코딩: 번역된 XML -> 게임이 읽는 .xml.e (디코더와 완전히 대칭인 역순 파이프라인)
python tools\decode_saves_xml_e.py <파일.xml> --encode --out-dir <출력 폴더>
```

복원된 원문은 `originalText/romfs/Saves/`에 원래 폴더 구조 그대로 저장되어 있습니다
(예: `originalText/romfs/Saves/item/itemData.xml`, `originalText/romfs/Saves/misogi/misogiKaiwa.xml`).
인코더는 디코더와 동일한 시드·상수를 역순으로 적용하며, 192개 파일 전부 디코드→인코드→디코드
왕복 시 원문과 바이트 단위로 일치함을 확인했습니다.

번역 파이프라인도 연결되어 있습니다. `tools/translate_saves_with_ollama.py`는 `originalText/romfs/Saves`를
재귀적으로 훑어 (속성 이름에 상관없이) 일본어가 포함된 모든 속성값을 찾아 로컬 모델로 번역하고
`translations/romfs/Saves/<같은 경로>`에 평문 XML로 기록합니다. 그 뒤 `tools/build_saves_data.py`가
`systemMessage`/`ui`를 제외한 나머지 폴더의 번역 XML을 한글 대체 문자로 치환하고 `.xml.e`로
재인코딩해 설치 폴더에 넣습니다. `translate_all.py`의 4단계(`4/4`)로도 연결되어 있으며, 아직 번역이
없는 폴더는 자동으로 건너뜁니다.

파일마다 실제 바이트 인코딩이 다르다는 점도 확인했습니다 — 대부분(item, achievement, misogi, tweet 등)은
CP932(Shift-JIS 상위 호환)이지만, `field/` 아래 파일들은 XML 선언이 `SHIFT_JIS`라고 되어 있음에도
실제로는 UTF-8입니다. 두 도구 모두 선언을 믿지 않고 실제 바이트를 UTF-8로 먼저 시도한 뒤 실패하면
CP932로 판정하는 방식으로 이 불일치를 자동 처리합니다.

### 아직 번역되지 않았거나 확인이 필요한 부분

- `Saves/*.xml.e`에 들어 있는 아이템명, 업적, 미소기 대화, SNS 패러디 대사 등은 추출·번역·재인코딩까지
  모두 완료했습니다. 원문에 일본어가 있던 속성값 14,499개 중 미번역으로 남은 것은 UI 레이아웃
  치수 측정용 더미 문자열(`あいうえお…`)과 아티스트 표기(`Origa・dottedline hiroko`)뿐입니다.
  실제로 번역이 필요한 XML은 25개이며, 나머지 167개는 일본어 텍스트가 없어 저장소에서 제외했습니다.
- 이번에 반영한 시스템 안내·시마법 선택 화면·일부 메뉴 설명·상점 대사 외의 UI 및 이미지로 그려진 일본어는 아직 번역되지 않은 부분이 있습니다.

  이미지(텍스처)에 일본어가 그려져 있어 텍스트 패치로는 해결되지 않는 항목은 다음과 같습니다.
  경로는 모두 `romfs/Data/NX/` 기준이며, 확인 시점 기준 존재하는 파일 수를 표시했습니다.

  **`ui/`** — 각 `.g1t`는 번호 붙은 하위 텍스처 여러 장을 담은 컨테이너입니다.

  | 파일 | 내용 |
  |---|---|
  | `acps3_bios_explanation*.g1t` (22개) | 바이오스 설명 |
  | `acps3_help*.g1t` (53개) | 튜토리얼 |
  | `system.g1t` | 시스템 메뉴 — **번역 완료** |
  | `title.g1t` | 타이틀 이미지 |
  | `window.g1t` | 아이템명 등 UI 곳곳에 쓰이는 것으로 추정 — **번역 완료** |
  | `common.g1t` | 01: 로그, 03: 시스템 등 — **번역 완료** |
  | `mainmenu.g1t` | 02: 아이템, 시스템 등 — **번역 완료** |
  | `network.g1t` | 네트워크 연결 확인 화면 |
  | `worldtown.g1t` | 지역 이름 등 맵 이동용 |

  **`Ipu/`**

  | 파일 | 내용 |
  |---|---|
  | `comp_tutorial1~3.g1t` | 요리 튜토리얼로 추정 |
  | `tu_battle*.g1t` (13개) | 전투 튜토리얼 |
  | `extra*.g1t` (42개) | 캐릭터 설정집·화보집 등 |
  | `set_frame.g1t` | 화면 위치 조절 화면(번역 불필요) |
  | `tu_bios*.g1t` (4개) | 바이오스 튜토리얼 |
  | `tu_combination*.g1t` (10개) | 콤비네이션 튜토리얼 |
  | `tu_comuling*.g1t` (6개) | 커뮤니케이션 링크 튜토리얼 |
  | `tu_dpselect*.g1t` (3개) | DP 선택지 튜토리얼 |
  | `tu_friend*.g1t` (4개) | 프렌드 기술 튜토리얼 |
  | `tu_genomap*.g1t` (2개) | 제노맵 이동 튜토리얼 |
  | `tu_genometrics*.g1t` (4개) | 제노메트릭스 튜토리얼 |
  | `tu_misogi*.g1t` (4개) | 미소기 튜토리얼로 추정 |

  `Ipu/`에서 `01Ion_*`, `02Cyas_*`처럼 캐릭터명이 붙은 파일이나 숫자로만 된 파일(`11.g1t` 등)은
  팬 일러스트·CG로 확인되어 번역 대상에서 제외했습니다.

  **위 목록에 없는 이미지도 더 있을 수 있습니다.** 전수 조사가 끝난 상태가 아니므로,
  플레이 중 일본어가 남아 있는 이미지를 발견하면 경로와 함께 [Issues](../../issues)에 제보해 주세요.
- 전체 플레이 검수가 완료된 상태는 아니므로 후반부에서 새로운 미번역·폰트 충돌이 발견될 수 있습니다.
- 희귀 한자 영역을 한글에 빌려 씁니다. 확인된 시마법 선택 화면의 동적 일본어 문자는 보호 목록에서 제외했지만, 아직 확인하지 못한 UI에서 충돌이 발견될 수 있습니다.

### 문제 제보

오역, 어색한 축약, 미번역 일본어, 글자 깨짐, 화면 멈춤이나 게임 종료 등 패치 사용 중 발견한 문제는 **GitHub의 [Issues 탭](../../issues)에 등록해 주세요.** README 댓글이나 커밋 메시지보다 Issues에 남겨야 문제별 진행 상황과 수정 이력을 관리할 수 있습니다.

가능하면 다음 정보를 함께 적어 주세요.

- 문제가 발생한 장면과 진행 상황
- 화면에 표시된 문구 또는 일본어 원문
- 스크린샷
- 사용 환경(Atmosphère 또는 Ryujinx)
- 게임 업데이트 1.0.1 설치 여부
- 동일한 방법으로 문제가 다시 발생하는지 여부
- 문제가 발생하기 직전의 세이브 파일(가능하면 ZIP으로 압축)

게임이 멈추거나 종료되는 문제는 직전에 선택한 메뉴와 재현 순서를 단계별로 적고, 같은 상황을 재현할 수 있는 세이브 파일을 함께 첨부해 주세요. 세이브에 사용자명·계정 정보 등 공개하면 안 되는 정보가 포함되어 있지 않은지 먼저 확인하세요. NSP/XCI/NCA, 타이틀 키, 펌웨어 등 정품 게임 데이터는 첨부하지 마세요.

## 4. 한글 폰트 처리 방식

게임은 EBM의 UTF-8 문자열을 읽지만 한글에 대응하는 내장 글리프와 문자→아틀라스 매핑이 없습니다. 단순히 한글 폰트 이미지만 넣어서는 어떤 한글이 어느 위치에 있는지 엔진이 알 수 없습니다.

이 패치는 다음 방식으로 해결했습니다.

1. 대사에 한자 2,097자를 순서대로 넣은 탐침 모드를 실행했습니다.
2. RenderDoc 캡처의 폰트 draw call 정점 버퍼에서 문자별 UV 좌표를 추출했습니다.
3. 기존에 화면으로 확인한 12개 문자와 대조해 매핑이 모두 일치하는지 검증했습니다.
4. 같은 셀을 공유하는 문자와 실제 UV 폭·높이가 24픽셀 미만인 문자를 제외했습니다.
5. 번역문에 남지 않은 희귀 한자 1,412개와 한글 음절 1,412자를 1:1로 연결했습니다.
6. 번역문의 한글은 대응 한자로 바꾸고, 그 한자가 가리키는 실제 UV 사각형에 한글 글리프를 그렸습니다.

초기에는 26픽셀 고정 격자에 글자를 그렸지만 실제 문자별 UV 좌상단이 최대 약 ±13픽셀 이동해 획이 잘렸습니다. 최종판은 고정 격자가 아니라 **각 문자의 실제 UV 사각형**에 그립니다.

상세 수식과 BC3 수정 방식은 [폰트 매핑 기술 문서](docs/FONT_MAPPING.md)를 참고하세요.

## 5. 직접 빌드하기

### 번역문 수정

대체 한자로 변환되기 전의 사람이 편집할 수 있는 한국어 파일은 `translations/romfs`에 들어 있습니다.

- `translations/romfs/Event/event/**/*.ebm`: 한국어 이벤트 대사 EBM 2,239개
- `translations/romfs/Saves/systemMessage/*.xml`: 한국어 시스템 메시지 XML 2개
- `translations/romfs/Saves/ui/**/*.xml`: 한국어 UI XML
- `translations/exefs/main_1.0.1.csv`: 업데이트 1.0.1 `main` 문자열의 원문·번역·주소·슬롯 크기
- `translations/exefs/main_1.0.1_manual_compaction.json`: 자동 축약으로 해결되지 않은 문구의 검수된 수동 축약표

`atmosphere/` 아래 파일은 게임에서 한글 폰트를 표시하기 위해 한글이 대체 한자로 변환된 설치용 결과물이므로 번역 수정에는 사용하지 마세요. EBM·XML 번역은 `translations/romfs`, 실행 파일 문자열은 `translations/exefs`에서 고친 뒤 아래 통합 빌드 명령으로 설치용 파일을 다시 생성합니다. `<CR>`, `<IMxx>`, `<RG>` 등의 제어문자는 위치까지 유지해야 합니다.

### 요구 사항

- Python 3
- NumPy
- Pillow
- 본인이 정품 게임에서 추출한 원본 `MainFont_nx_0.g1t`
- 한국어 번역이 반영된 `romfs/Event/event` 폴더

```powershell
pip install numpy pillow

python translate_all.py `
  --original-font "D:\path\to\MainFont_nx_0.g1t"
```

`translate_all.py`는 다음 작업을 순서대로 한 번에 처리합니다.

1. `translations/romfs/Event/event`의 한국어 EBM 변환
2. EBM, Saves XML과 `main` 번역에 사용된 모든 한글 음절의 폰트 생성
3. `translations/romfs/Saves` 아래 시스템 메시지와 UI XML 변환
4. 업데이트 1.0.1 `main` 문자열 IPS 생성
5. `atmosphere/contents/01003CF0128DE000/`과 `atmosphere/exefs_patches/`에 설치 가능한 결과물 출력

원본 폰트를 `original/romfs/Data/NX/Font/MainFont_nx_0.g1t`에 두면 `--original-font` 옵션 없이 `python translate_all.py`만 실행해도 됩니다. 한글↔대체 한자↔셀 대응표와 통계는 `build/final_mod_report.json`에 기록됩니다. `atmosphere/`와 `build/`는 생성 결과물이므로 Git에 포함되지 않습니다.

기본 글꼴은 저장소의 `fonts/Pretendard-Bold.otf`입니다. 다른 한글 글꼴을 사용하려면 `--font` 옵션으로 TTF/OTF 경로를 지정하고 해당 글꼴의 라이선스와 재배포 조건을 직접 확인해야 합니다.

### 도구별 상세 사용법

일반적인 번역 수정과 패치 생성에는 저장소 루트의 `translate_all.py`만 사용하면 됩니다. `tools/`의 개별 스크립트는 일부 결과만 다시 만들거나 폰트 매핑을 연구·검증할 때 사용하는 고급 도구입니다.

#### `translate_all.py` — 전체 패치 통합 빌드

다음 입력을 한 번에 처리합니다.

- `translations/romfs/Event/event/**/*.ebm`
- `translations/romfs/Saves/systemMessage/*.xml`
- `translations/romfs/Saves/ui/**/*.xml`
- `translations/exefs/main_1.0.1.csv`
- 정품 게임에서 추출한 원본 `MainFont_nx_0.g1t`

```powershell
python translate_all.py --original-font "D:\game\extracted\romfs\Data\NX\Font\MainFont_nx_0.g1t"
```

원본 폰트를 `original/romfs/Data/NX/Font/MainFont_nx_0.g1t`에 두면 다음처럼 실행할 수 있습니다.

```powershell
python translate_all.py
```

출력은 `atmosphere/contents/01003CF0128DE000/`에 생성됩니다. 실행할 때 이 Title ID 폴더의 이전 빌드 결과는 지우고 다시 생성합니다. 원본 폰트는 저작권이 있는 게임 파일이므로 Git에 추가하지 마세요.

#### `tools/build_final_korean_mod.py` — EBM과 폰트만 생성

한국어 EBM에 포함된 한글을 대체 한자로 바꾸고, 해당 대체 한자의 실제 UV 영역에 한글 글리프를 그린 폰트를 생성합니다.

```powershell
python tools/build_final_korean_mod.py `
  --translated-mod "translations" `
  --original-font "D:\game\extracted\romfs\Data\NX\Font\MainFont_nx_0.g1t" `
  --extra-text-dir "translations\romfs\Saves\systemMessage" `
  --output "build\mod" `
  --report "build\final_mod_report.json"
```

| 옵션 | 필수 | 설명 |
|---|:---:|---|
| `--translated-mod` | O | `romfs/Event/event`가 들어 있는 한국어 번역 루트 |
| `--original-font` | O | 정품 게임에서 추출한 원본 `MainFont_nx_0.g1t` |
| `--extra-text-dir` |  | 폰트 매핑에 포함할 추가 UTF-8 파일 폴더. 시스템 XML의 새 한글도 포함하려면 지정 |
| `--mapping` |  | RenderDoc에서 얻은 문자→UV 매핑 JSON. 기본값은 `data/char_to_cell_renderdoc.json` |
| `--probe` |  | 탐침 문자와 원문 출현 빈도 JSON. 기본값은 `data/probe_chars_full.json` |
| `--font` |  | 한글 글리프에 사용할 TTF/OTF. 기본값은 `fonts/Pretendard-Bold.otf` |
| `--output` |  | EBM과 폰트 출력 루트. 기본값은 `build/mod` |
| `--report` |  | 생성된 한글↔대체 문자 매핑과 통계 JSON |

`--output` 경로는 빌드할 때 먼저 삭제한 뒤 다시 생성되므로 번역 원본 폴더를 지정하면 안 됩니다. 시스템 메시지도 함께 배포할 때는 개별 실행보다 `translate_all.py` 사용을 권장합니다.

#### `tools/build_system_message.py` — Saves XML만 생성

사람이 읽을 수 있는 한국어 시스템 메시지·UI XML을 현재 폰트 매핑에 맞는 게임용 대체 문자 XML로 재귀 변환합니다. 시스템 XML의 `Text`와 UI XML의 `text` 속성을 모두 처리합니다.

게임의 텍스트 창은 표시 문자 20개마다 자체적으로 자동 줄바꿈합니다. `<CR>` 바로 앞 구간이 이미 20자 이상이면 자동 줄바꿈과 강제 줄바꿈이 겹칠 수 있습니다. 빌드 도구는 사쿠라대전4 한국어 패치와 같은 방식으로 해당 `<CR>`만 설치용 결과에서 제거하고 게임의 자동 줄바꿈에 맡깁니다. 이 규칙은 모든 이벤트 대사 EBM과 Saves XML의 `Text`·`text` 속성에 공통 적용되며 `translations/`의 편집용 파일은 변경하지 않습니다. 공백과 문장부호도 각각 한 칸이며 `<IMxx>` 같은 표시 제어 코드는 한 칸으로 계산합니다.

텍스트 창에는 최대 3줄만 표시되므로 한국어 번역문은 제어 코드를 제외하고 최대 60표시칸이어야 합니다. `tools/shorten_three_lines.py`는 60칸을 넘는 EBM·XML 번역문을 로컬 OpenAI 호환 모델로 축약하고, 60칸 이하 및 비-CR 제어문자 보존을 통과한 결과만 `translations/`에 반영합니다. `<#RRGGBB>` 색상 코드는 0칸, `<IMxx>` 같은 표시 요소는 1칸으로 계산합니다.

```powershell
python tools/build_system_message.py `
  --input "translations\romfs\Saves" `
  --mapping "build\final_mod_report.json" `
  --output "atmosphere\contents\01003CF0128DE000\romfs\Saves\systemMessage"
```

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--input` | `translations/romfs/Saves` | 편집 가능한 UTF-8 한국어 XML 루트 |
| `--mapping` | `build/final_mod_report.json` | 한글→대체 문자 매핑 보고서 |
| `--output` | Atmosphère의 `Saves/systemMessage` | 변환된 게임용 XML 출력 폴더 |

##### `SysInfo.xml` 인코딩 주의사항

편집용 `translations/romfs/Saves/systemMessage/SysInfo.xml`은 다른 번역 파일과 마찬가지로 UTF-8로 관리합니다. 다만 게임에 설치하는 `SysInfo.xml`은 반드시 원본과 같은 **Shift-JIS**로 생성해야 합니다. 이 파일을 읽는 HELP 문구 경로는 XML 선언보다 Shift-JIS 바이트 처리를 우선하는 것으로 보입니다. 설치용 파일을 UTF-8로 만들면 `매뉴얼을 표시합니다` 같은 문장이 `□ + 한자`가 섞인 모지바케로 출력됩니다. 메뉴 항목 등 다른 한국어가 정상인데 화면 아래 HELP 설명만 깨질 때 가장 먼저 이 문제를 확인하세요.

`tools/build_system_message.py`는 파일명이 `SysInfo.xml`일 때만 자동으로 Shift-JIS로 출력하고, `SysMess.xml`과 UI XML은 UTF-8로 출력합니다. 따라서 생성된 `atmosphere/` 파일을 직접 UTF-8로 다시 저장하지 말고 항상 `translate_all.py`로 재생성하세요. PowerShell에서는 다음 명령으로 설치용 파일의 선언을 확인할 수 있습니다.

```powershell
Get-Content "atmosphere\contents\01003CF0128DE000\romfs\Saves\systemMessage\SysInfo.xml" -TotalCount 1
```

정상 결과에는 `encoding='shift_jis'`가 표시되어야 합니다. 문제가 재발하면 다음 순서로 확인합니다.

1. `translate_all.py`로 전체 패치를 다시 빌드합니다.
2. 생성된 `SysInfo.xml` 첫 줄이 `shift_jis`인지 확인합니다.
3. 생성 파일과 실제 SD 카드 또는 Ryujinx 모드 폴더의 파일 해시를 비교합니다.
4. 게임과 Ryujinx를 완전히 종료한 상태에서 새 파일을 덮어쓴 뒤 다시 실행합니다.

번역에 기존 매핑에 없는 한글 음절을 새로 사용했다면 이 도구만 실행하지 말고 `translate_all.py`를 실행하세요. 통합 도구가 EBM과 XML을 함께 조사해 필요한 글리프를 다시 만들기 때문입니다. `<IMxx>`, `<RG>` 같은 제어문자는 원문 위치를 유지해야 합니다. `<CR>`도 편집용 번역에는 보존하되, 위의 20자 자동 줄바꿈 조건에 해당하면 EBM과 XML의 설치용 결과에서만 제거됩니다.

#### `tools/decode_renderdoc_font_draw.py` — RenderDoc 폰트 UV 해독

일반적인 패치 빌드에는 필요하지 않습니다. RenderDoc에서 폰트 draw call의 정점 버퍼를 추출한 경우, 탐침 문자열의 각 문자가 사용하는 UV 사각형과 셀 번호를 JSON으로 복원합니다.

```powershell
python tools/decode_renderdoc_font_draw.py `
  "capture\vertex_buffer.bin" `
  "data\probe_chars_full.json" `
  "build\char_to_cell.json" `
  --known "data\known_cells.json"
```

| 인자 | 설명 |
|---|---|
| `vertex_buffer` | 글리프당 6개 정점, 정점당 32바이트로 추출한 원시 정점 버퍼 |
| `probe_json` | 화면에 출력한 탐침 문자 순서가 들어 있는 JSON |
| `output_json` | 문자별 셀·UV 사각형을 기록할 결과 JSON |
| `--known` | 선택 사항. 이미 확인한 문자→셀 JSON과 결과를 교차 검증 |

정점 버퍼 크기가 `탐침 문자 수 × 6 × 32바이트`와 다르면 도구가 중단됩니다. RenderDoc 캡처와 원시 버퍼는 용량 및 게임 파생 데이터 문제로 저장소에 포함하지 않습니다.

### 번역 수정 시 주의사항

- EBM·XML은 반드시 `translations/romfs` 아래 파일을 수정하고 `atmosphere/`의 생성 결과물은 직접 고치지 마세요.
- 실행 파일 문자열은 `translations/exefs/main_1.0.1.csv`에서 수정하세요.
- EBM의 바이너리 구조, 레코드 수, 32바이트 메타데이터와 NUL 종료 형식을 보존해야 합니다.
- XML에서는 `Text` 외의 속성과 `<CR>`, `<IMxx>`, `<RG>` 같은 제어문자의 표기·순서·위치를 유지하세요.
- 새 한글 음절을 사용한 뒤에는 `translate_all.py`로 폰트까지 다시 생성하세요.
- 빌드가 끝나면 `atmosphere/contents/01003CF0128DE000`을 SD 카드 또는 Ryujinx 모드 폴더에 복사합니다.

### `main` 번역 수정 인수인계

GitHub Issue로 접수된 `main` 메뉴·지명·인명 등의 번역을 다음 작업자가 수정할 때는 아래 절차를 따릅니다.

1. 수정 전에 `translations/exefs/main_1.0.1.csv`를 백업합니다.
2. Issue의 일본어 원문을 CSV의 `original` 열에서 검색합니다.
3. 해당 행의 `translation`만 수정하고 `memory_address`, `rodata_offset`, `capacity_bytes`, `classification`, `original`은 바꾸지 않습니다.
4. 번역문의 UTF-8 바이트 수가 `capacity_bytes` 이하여야 합니다.
5. 초과하면 먼저 띄어쓰기를 제거하고, 그래도 길면 조사·주어·종결어미 또는 단어를 축약합니다.
6. `<CR>`, `<IMxx>`, printf 형식 등 제어문자는 원문과 철자·개수·순서가 같아야 합니다.
7. 사람이 최종 확인한 행은 `status`를 `needs_review`로 두고 `notes`에 수정 이유를 기록합니다.
8. `translate_all.py`로 폰트·ROMFS·IPS를 모두 다시 생성합니다.
9. `build/main_1.0.1_patch_report.json`에서 `skipped_records`가 0인지 확인한 뒤 게임에 적용합니다.

PowerShell에서 특정 번역문의 UTF-8 바이트 수를 확인하는 예시는 다음과 같습니다.

```powershell
$text = "수정한번역문"
[Text.Encoding]::UTF8.GetByteCount($text)
```

여러 초과 문장을 일괄 정리할 때는 현재 CSV를 반드시 백업한 뒤 다음 도구를 사용합니다.

```powershell
# 1. 공백 제거 후, 남은 초과 문장을 로컬 OpenAI 호환 모델로 축약
python tools/compact_main_translations.py

# 2. 사람이 검수한 수동 축약표를 적용하고 바이트·일본어·제어문자 검증
python tools/apply_main_compaction_overrides.py

# 3. 전체 폰트·ROMFS·IPS 재생성
python translate_all.py --original-font "D:\game\extracted\romfs\Data\NX\Font\MainFont_nx_0.g1t"
```

자동 축약으로 해결되지 않은 항목은 `translations/exefs/main_1.0.1_manual_compaction.json`에 `index: 번역문` 형식으로 추가합니다. `tools/apply_main_compaction_overrides.py`는 다음 조건을 하나라도 위반하면 CSV를 수정하지 않고 중단합니다.

- UTF-8 번역 바이트 수가 슬롯 용량을 초과함
- 번역문에 일본어가 남아 있음
- 원문의 제어문자와 번역문의 제어문자 개수·순서가 다름
- 축약표의 index가 CSV에 없음

`tools/build_main_text_patch.py`도 용량을 다시 확인하며, 초과하거나 폰트 매핑에 없는 한글이 있는 문장은 IPS에서 제외하고 `build/main_1.0.1_patch_report.json`에 이유를 기록합니다. 정상 배포 조건은 `patched_records`가 번역 대상 수와 일치하고 `skipped_records`가 0인 상태입니다.

#### 포인터 재배치 관련 주의

길이 제한을 피하려고 번역문을 `main`의 0영역으로 옮기고 포인터 또는 AArch64 `ADRP+ADD`를 수정하는 시험을 진행한 적이 있습니다. 775개 문자열과 2,097개 참조의 기계 검증은 통과했지만, 일부 0영역이 실제 더미가 아니라 시스템 전환용 테이블이어서 시스템 메뉴에서 메인 메뉴로 돌아갈 때 게임이 멈췄습니다.

따라서 현재 배포판에서는 다음 파일을 분석·연구 목적으로만 사용하고 결과물을 배포 IPS에 합치지 않습니다.

- `tools/analyze_main_references.py`
- `tools/build_pointer_relocation_patch.py`
- `tools/validate_pointer_patch.py`

포인터 재배치를 다시 연구하려면 임의의 연속 0바이트를 빈 공간으로 간주하지 말고, 해당 영역이 어떤 경로에서도 참조되지 않는다는 사실을 먼저 확인해야 합니다. 반드시 기존 IPS와 번역 CSV, Ryujinx 모드 폴더를 백업하고 별도 시험본으로 검증하세요. 최소 확인 항목은 게임 시작, 세이브·로드, 시스템 메뉴 진입, **시스템 메뉴에서 메인 메뉴로 복귀**, 전투 진입·종료입니다.

## 6. 개발 내역

- **EBM 구조**: 파일 선두 레코드 수와 레코드별 32바이트 메타데이터, UTF-8 바이트 길이, NUL 종료 문자열 구조로 처리합니다.
- **폰트 텍스처**: BC3(DXT5), 2048×1024. 색상 데이터와 선택하지 않은 압축 블록은 원본 그대로 유지합니다.
- **글리프 가독성**: 원본 일본어 폰트를 참고해 약 20×20픽셀로 확대하고 BC4 8단계 알파 안티앨리어싱을 적용했습니다.
- **RenderDoc 추출**: 글리프당 6개 정점의 UV `float2`를 읽어 2,097개 문자의 셀과 실제 샘플 사각형을 확보했습니다.
- **중복 방지**: 동일 폰트 셀을 공유하는 30개 셀은 후보에서 전부 제외했습니다.
- **실제 UV 배치**: 폭·높이가 모두 24픽셀 이상인 고유 영역만 사용했습니다.
- **텍스트 치환**: 완성형 한글과 CJK 한자는 UTF-8에서 모두 3바이트이므로 파일 크기를 유지하며 치환할 수 있습니다.
- **실행 파일 문자열**: 번역문을 원래 슬롯 안에만 기록하고, 초과 문장은 공백 제거 후 의미 보존 축약을 적용합니다. 포인터 재배치나 임의 0영역 사용은 하지 않습니다.
- **시스템 HELP 인코딩**: 편집 원본은 UTF-8로 유지하되, 설치용 `SysInfo.xml`만 원본 로더에 맞춰 Shift-JIS로 생성합니다.
- **전수 검증**: 패치 EBM을 역치환해 번역 원본과 바이트 단위로 비교했습니다.
- **`Saves/*.xml.e` 버전 1 디코더**: `main` 실행 파일 디스어셈블로 버전 1 전용 PRNG 상수를 알아내고, gust_tools가 공개한 ANP 시드와 조합해 192개 파일 전부 체크섬 검증 통과.

## 7. 저장소 구성

| 경로 | 내용 |
|---|---|
| `atmosphere/` | 설치 가능한 LayeredFS 패치 |
| `translations/romfs/Event/event/` | 수정 가능한 한국어 이벤트 대사 EBM 2,239개 |
| `translations/romfs/Saves/systemMessage/` | 수정 가능한 한국어 시스템 메시지 XML |
| `translations/romfs/Saves/ui/` | 수정 가능한 한국어 UI XML |
| `translations/exefs/main_1.0.1.csv` | 업데이트 1.0.1 실행 파일 문자열의 원문·번역·주소·슬롯 크기 |
| `translations/exefs/main_1.0.1_manual_compaction.json` | 슬롯 제한 때문에 직접 검수한 축약 번역표 |
| `data/char_to_cell_renderdoc.json` | 일본어 문자별 셀·UV 사각형 |
| `data/probe_chars_full.json` | 탐침 문자 목록과 원문 출현 빈도 |
| `data/protected_ui_chars.json` | 한글 대체 대상으로 사용하지 않을 동적 UI 문자 목록 |
| `docs/FONT_MAPPING.md` | 폰트 분석 기술 문서 |
| `fonts/Pretendard-Bold.otf` | 한글 글리프 생성에 사용하는 Pretendard Bold |
| `tools/build_final_korean_mod.py` | 최종 EBM·폰트 생성기 |
| `tools/build_system_message.py` | 한국어 systemMessage/ui XML을 설치용 대체 문자 XML(평문)로 변환 |
| `tools/build_saves_data.py` | 한국어 Saves XML(item·misogi·tweet 등)을 대체 문자로 치환 후 `.xml.e`로 재인코딩 |
| `tools/translate_saves_with_ollama.py` | `originalText/romfs/Saves`의 일본어 속성을 추출해 로컬 모델로 번역, `translations/romfs/Saves`에 기록 |
| `tools/build_main_text_patch.py` | `main_1.0.1.csv`를 검증하고 고정 길이 IPS 생성 |
| `tools/inline_tail_fix.py` | 컴파일러가 `.text`에 상수로 심어 둔 짧은 문자열의 꼬리 바이트와 SSO 길이 필드를 함께 패치 |
| `tools/balloonsel.py` | 대화 선택지 `balloonseldata.bsb` 파서/작성기 |
| `tools/translate_balloonsel.py` | 선택지 추출 후 로컬 모델로 번역 |
| `tools/build_balloonsel.py` | 번역된 선택지를 대체 문자로 치환해 `.bsb`로 재작성 |
| `tools/build_event_sysmess.py` | 이벤트 스크립트(`.ebd`)의 `SYS:MESS` 시스템 메시지를 같은 바이트 길이로 치환 |
| `tools/build_ui_images.py` | 직접 번역한 UI 텍스처(`translateImage/*.g1t`)를 검증 후 설치 폴더에 배치 |
| `tools/expand_main_compaction.py` | 슬롯 여유가 남는데도 과하게 줄어든 `main` 번역을 자연스럽게 복원 |
| `tools/restore_fullwidth_punctuation.py` | ASCII로 바뀐 전각 문장부호를 원본대로 되돌림 |
| `tools/build_fps_unlock_patch.py` | 30FPS 제한 해제 IPS 생성(한국어 패치와 무관하게 단독 사용 가능) |
| `tools/compact_main_translations.py` | 초과 문장의 공백 제거 및 로컬 모델 단어 축약 |
| `tools/apply_main_compaction_overrides.py` | 검수된 수동 축약표 적용 및 바이트·제어문자 검증 |
| `translate_all.py` | EBM·폰트·시스템 메시지·UI를 한 번에 생성하는 통합 실행 파일 |
| `tools/decode_renderdoc_font_draw.py` | RenderDoc 정점 버퍼 해독기 |
| `tools/decode_saves_xml_e.py` | `Saves/*.xml.e`(버전 1 Gust 스크램블) 디코더/인코더, 평문 XML과 상호 변환 |
| `originalText/romfs/Saves/` | 위 도구로 복원한 `Saves/*.xml` 원문(일본어). 번역본은 `translations/romfs/Saves/` |

저장소에 포함되지 않는 항목:

- NSP/XCI/NCA, 타이틀 키, 펌웨어 등 게임 원본 데이터
- 원본 `MainFont_nx_0.g1t`
- RenderDoc `.rdc` 캡처와 원시 정점 버퍼
- Ryujinx 사용자 설정 및 세이브 데이터
- 로컬 번역 작업 환경과 개인 경로

## 8. 라이선스 / 권리

**별도의 연락이나 허락 없이 이 프로젝트를 내려받아 적용하거나, 저장소를 포크해 참고·수정할 수 있습니다.** 다만 각 구성요소의 권리는 서로 다릅니다.

- **도구 소스코드** (`tools/*.py`): [MIT 라이선스](LICENSE)를 따릅니다.
- **프로젝트 문서와 자체 제작 매핑 데이터** (`docs/`, `data/*.json`): 비영리 팬 번역·연구·보존 목적으로 출처를 표시하고 공유·수정할 수 있습니다. 게임 또는 패치를 판매하는 상업적 용도로 사용하지 마세요.
- **한국어 번역문**: 프로젝트 참여자가 작성한 2차적 번역물입니다. 비영리 팬 번역 목적으로 공유·수정할 수 있으나 원작의 권리까지 허가하는 것은 아닙니다.
- **게임 파생 패치 파일** (`atmosphere/`): 원본 게임의 파일 형식·데이터 일부를 바탕으로 생성되었으며 MIT 라이선스 대상이 아닙니다. 정품 게임 소유자가 개인적으로 적용하는 비영리 팬 패치 용도로만 제공됩니다.
- **Pretendard 글꼴** (`fonts/Pretendard-Bold.otf`): [SIL Open Font License 1.1](fonts/Pretendard-LICENSE.txt)을 따릅니다. 최종 폰트 아틀라스의 한글 글리프도 Pretendard Bold를 사용해 생성했습니다.
- **게임 원작**: 『Ar nosurge』 및 관련 상표·그래픽·텍스트·데이터의 권리는 KOEI TECMO GAMES/Gust 및 각 권리자에게 있습니다. 이 프로젝트는 해당 회사들과 관련이 없으며 어떠한 권리도 주장하지 않습니다.

패치 사용으로 발생하는 게임 파일 손상, 세이브 손실, 기기·에뮬레이터 문제에 대해 프로젝트 참여자는 책임지지 않습니다. 적용 전 원본과 세이브를 백업해 주세요.
