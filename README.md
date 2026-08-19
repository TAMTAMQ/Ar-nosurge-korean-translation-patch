# 아르노서지 DX 한국어 번역 패치

> 🙏 이 패치는 **AI 번역 기반이라 발생할 수 있는 오역이나 어색한 표현을 크게 개의치 않고 플레이하실 수 있는 분들을 위한 비공식 팬 패치**입니다.

> ⚠️ **완전 한글화 패치가 아닙니다.** 이벤트 대사 대부분은 번역되어 있지만, 대사 EBM과 별도로 관리되는 화자명·메뉴·그래픽 문구 등은 일본어로 남아 있을 수 있습니다.
>
> ⚠️ 화자 정보가 원문 텍스트만으로 명확하지 않은 장면은 같은 인물의 존댓말/반말이나 말투가 일관되지 않을 수 있습니다.

Nintendo Switch판 『Ar nosurge: Ode to an Unborn Star DX』(アルノサージュ ～生まれいずる星へ祈る詩～ DX)의 비공식 한국어 번역 패치입니다.

- 이벤트 대사 파일 2,239개를 번역합니다.
- 시스템·메뉴·상점 대사 XML 2개(472개 항목)를 번역합니다.
- 고유 한글 음절 1,372자를 게임 내장 폰트 아틀라스에 새로 매핑했습니다.
- 원본 NSP/XCI를 수정하지 않고 Atmosphère/Ryujinx의 LayeredFS 모드로 적용합니다.
- 폰트 매핑 추출, 번역문 치환, 폰트 생성 과정을 Python 소스로 공개합니다.

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
```

### 2-2. Ryujinx

1. 게임 목록에서 아르노서지를 우클릭하고 모드 폴더를 엽니다.
2. `korean_final` 같은 임의의 폴더를 하나 만듭니다.
3. 그 안에 저장소의 `atmosphere/contents/01003CF0128DE000/romfs` 폴더를 복사합니다.

```text
mods/contents/01003cf0128de000/korean_final/romfs/...
```

기존 대사·폰트 시험 모드가 함께 활성화되어 있으면 충돌할 수 있으므로 다른 모드는 비활성화해 주세요.

## 3. 패치 내용

| 영역 | 수량 | 상태 |
|---|---:|---|
| 이벤트 대사 EBM | 2,239개 | 한국어 번역 및 한자 대체 코드 적용 |
| 시스템 메시지 XML | 2개, 472개 항목 | 한국어 번역 및 한자 대체 코드 적용 |
| 고유 한글 음절 | 1,372자 | 게임 폰트 아틀라스에 추가 |
| 한글 출현 수 | 987,758회 | 전부 대체 코드로 변환 |
| 메인 폰트 | 1개 | `MainFont_nx_0.g1t` 알파 블록 수정 |
| EBM 구조 검증 | 2,239개 | 오류 0건 |
| 역변환 검증 | 2,239개 | 원 번역본과 불일치 0건 |

### 아직 번역되지 않았거나 확인이 필요한 부분

- 화자명(예: `デルタ`)은 이벤트 대사와 별도 리소스라 일본어로 남아 있습니다.
- 이번에 반영한 시스템 안내·일부 메뉴 설명·상점 대사 외의 아이템명, UI 및 이미지로 그려진 일본어는 아직 번역되지 않은 부분이 있습니다.
- 전체 플레이 검수가 완료된 상태는 아니므로 후반부에서 새로운 미번역·폰트 충돌이 발견될 수 있습니다.
- 희귀 한자 영역을 한글에 빌려 쓰므로, 해당 한자가 별도 UI에서 사용되는 장면이 있다면 그 UI가 한글 음절로 보일 가능성이 있습니다.

## 4. 한글 폰트 처리 방식

게임은 EBM의 UTF-8 문자열을 읽지만 한글에 대응하는 내장 글리프와 문자→아틀라스 매핑이 없습니다. 단순히 한글 폰트 이미지만 넣어서는 어떤 한글이 어느 위치에 있는지 엔진이 알 수 없습니다.

이 패치는 다음 방식으로 해결했습니다.

1. 대사에 한자 2,097자를 순서대로 넣은 탐침 모드를 실행했습니다.
2. RenderDoc 캡처의 폰트 draw call 정점 버퍼에서 문자별 UV 좌표를 추출했습니다.
3. 기존에 화면으로 확인한 12개 문자와 대조해 매핑이 모두 일치하는지 검증했습니다.
4. 같은 셀을 공유하는 문자와 실제 UV 폭·높이가 24픽셀 미만인 문자를 제외했습니다.
5. 번역문에 남지 않은 희귀 한자 1,372개와 한글 음절 1,372자를 1:1로 연결했습니다.
6. 번역문의 한글은 대응 한자로 바꾸고, 그 한자가 가리키는 실제 UV 사각형에 한글 글리프를 그렸습니다.

초기에는 26픽셀 고정 격자에 글자를 그렸지만 실제 문자별 UV 좌상단이 최대 약 ±13픽셀 이동해 획이 잘렸습니다. 최종판은 고정 격자가 아니라 **각 문자의 실제 UV 사각형**에 그립니다.

상세 수식과 BC3 수정 방식은 [폰트 매핑 기술 문서](docs/FONT_MAPPING.md)를 참고하세요.

## 5. 직접 빌드하기

### 번역문 수정

대체 한자로 변환되기 전의 사람이 편집할 수 있는 한국어 파일은 `translations/romfs`에 들어 있습니다.

- `translations/romfs/Event/event/**/*.ebm`: 한국어 이벤트 대사 EBM 2,239개
- `translations/romfs/Saves/systemMessage/*.xml`: 한국어 시스템 메시지 XML 2개

`atmosphere/` 아래 파일은 게임에서 한글 폰트를 표시하기 위해 한글이 대체 한자로 변환된 설치용 결과물이므로 번역 수정에는 사용하지 마세요. 번역은 `translations/romfs`에서 고친 뒤 아래 통합 빌드 명령으로 설치용 파일을 다시 생성합니다. `<CR>`, `<IMxx>`, `<RG>` 등의 제어문자는 위치까지 유지해야 합니다.

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
2. EBM과 시스템 메시지에 사용된 모든 한글 음절의 폰트 생성
3. `translations/romfs/Saves/systemMessage`의 한국어 XML 변환
4. `atmosphere/contents/01003CF0128DE000/`에 설치 가능한 결과물 출력

원본 폰트를 `original/romfs/Data/NX/Font/MainFont_nx_0.g1t`에 두면 `--original-font` 옵션 없이 `python translate_all.py`만 실행해도 됩니다. 한글↔대체 한자↔셀 대응표와 통계는 `build/final_mod_report.json`에 기록됩니다. `atmosphere/`와 `build/`는 생성 결과물이므로 Git에 포함되지 않습니다.

기본 글꼴은 저장소의 `fonts/Pretendard-Bold.otf`입니다. 다른 한글 글꼴을 사용하려면 `--font` 옵션으로 TTF/OTF 경로를 지정하고 해당 글꼴의 라이선스와 재배포 조건을 직접 확인해야 합니다.

### 도구별 상세 사용법

일반적인 번역 수정과 패치 생성에는 저장소 루트의 `translate_all.py`만 사용하면 됩니다. `tools/`의 개별 스크립트는 일부 결과만 다시 만들거나 폰트 매핑을 연구·검증할 때 사용하는 고급 도구입니다.

#### `translate_all.py` — 전체 패치 통합 빌드

다음 입력을 한 번에 처리합니다.

- `translations/romfs/Event/event/**/*.ebm`
- `translations/romfs/Saves/systemMessage/*.xml`
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

#### `tools/build_system_message.py` — 시스템 메시지 XML만 생성

사람이 읽을 수 있는 한국어 XML을 현재 폰트 매핑에 맞는 게임용 대체 문자 XML로 변환합니다.

```powershell
python tools/build_system_message.py `
  --input "translations\romfs\Saves\systemMessage" `
  --mapping "build\final_mod_report.json" `
  --output "atmosphere\contents\01003CF0128DE000\romfs\Saves\systemMessage"
```

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--input` | `translations/romfs/Saves/systemMessage` | 편집 가능한 UTF-8 한국어 XML 폴더 |
| `--mapping` | `build/final_mod_report.json` | 한글→대체 문자 매핑 보고서 |
| `--output` | Atmosphère의 `Saves/systemMessage` | 변환된 게임용 XML 출력 폴더 |

번역에 기존 매핑에 없는 한글 음절을 새로 사용했다면 이 도구만 실행하지 말고 `translate_all.py`를 실행하세요. 통합 도구가 EBM과 XML을 함께 조사해 필요한 글리프를 다시 만들기 때문입니다. `<CR>` 같은 제어문자는 원문과 같은 위치에 유지해야 합니다.

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

- 반드시 `translations/romfs` 아래 파일을 수정하고 `atmosphere/`의 생성 결과물은 직접 고치지 마세요.
- EBM의 바이너리 구조, 레코드 수, 32바이트 메타데이터와 NUL 종료 형식을 보존해야 합니다.
- XML에서는 `Text` 외의 속성과 `<CR>`, `<IMxx>`, `<RG>` 같은 제어문자의 표기·순서·위치를 유지하세요.
- 새 한글 음절을 사용한 뒤에는 `translate_all.py`로 폰트까지 다시 생성하세요.
- 빌드가 끝나면 `atmosphere/contents/01003CF0128DE000`을 SD 카드 또는 Ryujinx 모드 폴더에 복사합니다.

## 6. 개발 내역

- **EBM 구조**: 파일 선두 레코드 수와 레코드별 32바이트 메타데이터, UTF-8 바이트 길이, NUL 종료 문자열 구조로 처리합니다.
- **폰트 텍스처**: BC3(DXT5), 2048×1024. 색상 데이터와 선택하지 않은 압축 블록은 원본 그대로 유지합니다.
- **글리프 가독성**: 원본 일본어 폰트를 참고해 약 20×20픽셀로 확대하고 BC4 8단계 알파 안티앨리어싱을 적용했습니다.
- **RenderDoc 추출**: 글리프당 6개 정점의 UV `float2`를 읽어 2,097개 문자의 셀과 실제 샘플 사각형을 확보했습니다.
- **중복 방지**: 동일 폰트 셀을 공유하는 30개 셀은 후보에서 전부 제외했습니다.
- **실제 UV 배치**: 폭·높이가 모두 24픽셀 이상인 고유 영역만 사용했습니다.
- **텍스트 치환**: 완성형 한글과 CJK 한자는 UTF-8에서 모두 3바이트이므로 파일 크기를 유지하며 치환할 수 있습니다.
- **전수 검증**: 패치 EBM을 역치환해 번역 원본과 바이트 단위로 비교했습니다.

## 7. 저장소 구성

| 경로 | 내용 |
|---|---|
| `atmosphere/` | 설치 가능한 LayeredFS 패치 |
| `translations/romfs/Event/event/` | 수정 가능한 한국어 이벤트 대사 EBM 2,239개 |
| `translations/romfs/Saves/systemMessage/` | 수정 가능한 한국어 시스템 메시지 XML |
| `data/char_to_cell_renderdoc.json` | 일본어 문자별 셀·UV 사각형 |
| `data/probe_chars_full.json` | 탐침 문자 목록과 원문 출현 빈도 |
| `docs/FONT_MAPPING.md` | 폰트 분석 기술 문서 |
| `fonts/Pretendard-Bold.otf` | 한글 글리프 생성에 사용하는 Pretendard Bold |
| `tools/build_final_korean_mod.py` | 최종 EBM·폰트 생성기 |
| `tools/build_system_message.py` | 한국어 XML을 설치용 대체 문자 XML로 변환 |
| `translate_all.py` | EBM·폰트·시스템 메시지를 한 번에 생성하는 통합 실행 파일 |
| `tools/decode_renderdoc_font_draw.py` | RenderDoc 정점 버퍼 해독기 |

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
