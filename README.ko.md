# Fal.ai-Seedream5-Layers-To-Save-PSD

*다른 언어로 읽기: [English](README.md)*

fal.ai [Seedream 5 Pro **Layerize**](https://fal.ai/models/bytedance/seedream/v5/pro/layerize) 결과를 **Embedded Smart Objects PSD**로 저장한다 — AI가 분리한 모든 오브젝트 레이어가 납작한 래스터가 아니라, 원본 해상도 그대로 임베드된 진짜 스마트 오브젝트로 들어간다. Photoshop 설치 없이 순수 Python으로 동작한다.

**⬇ 다운로드:** [최신 릴리즈](https://github.com/coeyes/Fal.ai-Seedream5-Layers-To-Save-PSD/releases/latest)에서 단독 실행 Windows exe를 받을 수 있다 — Python 설치 불필요.

## 개요

[Seedream 5 Pro Layerize](https://fal.ai/models/bytedance/seedream/v5/pro/layerize)는 한 장의 이미지를 AI로 오브젝트별 레이어(투명 PNG)로 분해하고, 각 레이어의 URL·이름·배치 정보(bounding box)를 JSON으로 내려준다. 이 도구는 그 JSON을 받아:

1. 각 레이어 PNG를 다운로드하고
2. `z_index=0`(배경, 이름 없음 → `background`) 크기로 PSD 캔버스를 만들고
3. 각 PNG를 **고해상도 원본 그대로 임베드한 스마트 오브젝트**로 만들어, bounding box 위치·크기로 트랜스폼 배치해 z_index 순서로 쌓는다

레이어 PNG는 최종 배치 크기보다 약 2배 고해상도라서, 스마트 오브젝트로 임베드하면 포토샵에서 확대·재배치해도 화질 손실이 없다.

## fal.ai에서 JSON 가져오기

1. fal.ai 플레이그라운드에서 [Seedream 5 Pro Layerize](https://fal.ai/models/bytedance/seedream/v5/pro/layerize)를 실행한다.
2. Result가 **Completed**가 되면 결과 보기를 **JSON**으로 전환한다 (아래 빨간 박스):

   ![결과 보기를 JSON으로 전환](assets/fal-layerize-01.png)

3. JSON 전체를 복사한다 — 패널에 복사 버튼이 있다 (아래 빨간 박스):

   ![결과 JSON 복사](assets/fal-layerize-02.png)

## GUI

```bat
python gui.py
```

![GUI](assets/gui.png)

복사한 JSON을 텍스트 영역에 붙여넣고, 출력 폴더와 파일명을 정한 뒤 **실행**을 누르면 된다. 진행 상황과 결과는 하단 status 로그에 표시된다. UI 언어: English / 한국어 / 日本語 (OS 로케일 자동 감지).

## CLI

```bat
.venv\Scripts\activate
python make_psd.py layer.json          @REM layer.psd + layer.psd_layers/ 생성
python make_psd.py layer.json -o my.psd
python make_psd.py layer.json --gen-layers-folder 0   @REM PSD만 생성
```

출력 기본값은 `<json 파일명>.psd` (예: `layer.json` → `layer.psd`).

기본으로 `<output.psd>_layers` 폴더에 각 레이어 원본 PNG를 `<zindex>_<layername>.png`로 함께 저장한다. 레이어 이름의 파일명 금지 문자는 `_`로 치환되고, 대소문자 무시 중복(z0의 `background` 포함)은 `_2`, `_3` 접미사로 구분된다.

## 설치

```bat
uv venv --seed
.venv\Scripts\activate
uv pip install -r requirements.txt
```

의존성: `psd-tools`, `pillow` (Python 3.12에서 테스트).

### 단독 실행 바이너리 빌드

```bat
build.bat      @REM Windows: dist\Fal.ai-Seedream5-Layers-To-Save-PSD.exe (단일 파일, 콘솔 없음)
```

```sh
bash build.sh  # macOS: dist/Fal.ai-Seedream5-Layers-To-Save-PSD.dmg (.app 포함)
```

두 스크립트 모두 `icon.png`를 플랫폼 아이콘 포맷으로 변환한 뒤 PyInstaller로 패키징한다. GitHub 릴리즈를 발행하면 [워크플로](.github/workflows/release.yml)가 Windows exe와 macOS dmg를 빌드해 릴리즈에 자동 첨부한다.

## 동작 원리 (요약)

psd-tools는 스마트 오브젝트 *생성*을 공식 지원하지 않는다. 이 도구는 psd-tools의 저수준 직렬화 계층을 이용해 스마트 오브젝트 블록(`SoLd`, `PlLd`, 전역 `lnk2`)을 직접 조립한다. 디스크립터 구조는 Photoshop이 실제로 기록한 바이너리를 base64 템플릿으로 임베드해 두고, uuid·트랜스폼·크기만 런타임에 패치하는 방식이라 견고하다.

또한 psd-tools의 알려지지 않은 버그 — `LinkedLayer` v8 꼬리의 `contentID` 디스크립터를 누락 기록해 **Photoshop이 파일을 아예 열지 못하게 되는 문제** — 를 `LinkedLayerV8` 서브클래스로 우회한다. 포맷 구조, 템플릿 패치 전략, 버그 규명 과정 등 기술 상세는 [TECH.ko.md](TECH.ko.md) 참조.

## 검증

Photoshop 27.6에서 실제로 열어 8개 레이어 전부 `LayerKind.SMARTOBJECT`로 인식됨을 확인했고, 포토샵이 flatten-export한 PNG(`ps_export.png`)가 기대 썸네일(`final_thumb.png`)과 일치한다. psd-tools 재파싱 검증 스크립트는 `_ref/verify.py`.

## 파일

- `make_psd.py` — 코어 / CLI 스크립트
- `gui.py` — tkinter GUI 래퍼
- `layer.json` / `final_thumb.png` — 테스트 입력 / 기대 결과
- `TECH.md` / `TECH.ko.md` — 기술 문서: PSD 스마트 오브젝트 바이너리 구조와 생성 기법
- `CHANGELOG.md` — 릴리즈 이력

## 라이선스 / 저자

MIT License — [LICENSE](LICENSE) 참조.

저자: **Hyeongjik Song** <coeyes@gmail.com>, [<img src="assets/studio-animal-logo-full.svg" alt="studio animal logo" height="25">Studio Animal Inc.](http://www.studioanimal.co.kr/)
