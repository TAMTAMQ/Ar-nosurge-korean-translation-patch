# 제3자 권리 고지

## Ar nosurge

『Ar nosurge: Ode to an Unborn Star DX』, 관련 상표, 캐릭터, 그래픽, 원문 텍스트 및 게임 데이터의 권리는 KOEI TECMO GAMES/Gust와 각 권리자에게 있습니다.

이 저장소는 비공식·비영리 팬 번역 프로젝트이며 원작사, 유통사, Nintendo, 에뮬레이터 개발팀과 관련이 없습니다. 저장소의 MIT 라이선스는 게임 원본이나 게임에서 파생된 데이터에 적용되지 않습니다.

## Pretendard

현재 배포용 폰트 아틀라스의 한글은 `Pretendard-Bold.otf`를 래스터화하여 생성했습니다. Pretendard는 SIL Open Font License 1.1로 배포됩니다.

- 저작권 및 전체 OFL 본문은 `fonts/Pretendard-LICENSE.txt`에 포함되어 있습니다.
- 저장소에 포함된 `Pretendard-Bold.otf`는 원래 글꼴 이름을 변경하지 않은 원본 글꼴 파일입니다.
- 다른 글꼴로 재빌드하는 사용자는 해당 글꼴의 사용·수정·배포 조건을 직접 확인해야 합니다.

## 60FPS 프레임 해제 패치

프레임 제한이 걸리는 지점(`0x3D07CC` 부근)은 DeathChaos25의 비공식 영문 패치
[ArNosurgeDeluxeSwitchEngPatch](https://github.com/DeathChaos25/ArNosurgeDeluxeSwitchEngPatch)에서
확인했습니다. 해당 프로젝트는 Skyline 플러그인으로 같은 지점을 후킹합니다.

이 저장소에는 해당 프로젝트의 코드나 바이너리를 포함하지 않습니다.
`tools/build_fps_unlock_patch.py`가 생성하는 IPS는 게임 명령어 1바이트를 바꾸는
독립적인 패치이며, 영문 UI 치환 등 다른 기능은 포함하지 않습니다.

## gust_enc (Saves/*.xml.e 디코더)

`tools/decode_saves_xml_e.py`는 `Saves/` 아래의 게임 데이터 XML이 담긴 Gust `.e`
포맷을 평문 XML로 복원하고(디코드), 번역한 XML을 다시 그 포맷으로 되돌립니다(인코드).
압축("Glaze") 알고리즘 구조는 VitaSmith의
[gust_tools](https://github.com/VitaSmith/gust_tools) (`gust_enc.c`, GPLv3)가
공개 문서([gust_enc 설명 gist](https://gist.github.com/VitaSmith/ab384400bd992413ee0da401457abee1))로
설명한 내용을 참고해 Python으로 새로 작성했습니다.

이 게임은 gust_tools가 지원하지 않는 스크램블링 "버전 1"을 사용합니다
(공개 도구는 버전 2·3만 지원하며, 담당자도 이 버전은 확보하지 못해 구현을
포기했다고 밝힌 바 있습니다). 버전 1에 필요한 전역 PRNG 상수
(`RANDOM_INCREMENT=0x2fa5`, 주 스크램블 상수 `0x3b9a728b`)는 이 저장소에서
Switch용 `main` 실행 파일을 직접 디스어셈블해 알아냈습니다. 게임별 시드 값은
gust_tools가 이미 공개한 `gust_enc.json`의 "ANP"(Ar nosurge Plus) 항목을
그대로 사용했으며, 체크섬 검증을 통해 정확함을 확인했습니다.

이 저장소는 gust_tools의 코드나 바이너리를 포함하지 않으며, `decode_saves_xml_e.py`는
공개된 알고리즘 설명을 바탕으로 독립적으로 작성한 구현입니다. GPLv3인 gust_enc.c의
압축/압축 해제("Glaze") 로직 구조를 상당히 가깝게 따르는 점을 밝혀둡니다.

## RenderDoc

RenderDoc은 폰트 UV 분석 과정에서만 사용했습니다. RenderDoc 실행 파일, 라이브러리 및 캡처 파일은 이 저장소에 포함되지 않습니다. `data/char_to_cell_renderdoc.json`은 캡처에서 프로젝트가 추출한 수치형 분석 결과입니다.

## Python 의존성

빌드 도구는 NumPy와 Pillow를 사용합니다. 해당 패키지 자체는 저장소에 번들하지 않으며 각 프로젝트의 라이선스를 따릅니다.
