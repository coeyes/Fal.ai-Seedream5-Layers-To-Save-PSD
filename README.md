# seedream5_layer

seedream5pro **layerize** 결과 JSON을 입력받아, AI가 분리한 오브젝트 레이어들을 **임베디드 스마트 오브젝트**로 쌓은 PSD를 생성하는 도구다. Photoshop 설치 없이 순수 Python으로 동작한다.

## 개요

seedream5pro layerize는 한 장의 이미지를 AI로 오브젝트별 레이어(투명 PNG)로 분해하고, 각 레이어의 URL·이름·배치 정보(bounding box)를 JSON으로 내려준다. 이 도구는 그 JSON을 받아:

1. 각 레이어 PNG를 다운로드하고
2. `z_index=0`(배경, 이름 없음 → `background`) 크기로 PSD 캔버스를 만들고
3. 각 PNG를 **고해상도 원본 그대로 임베드한 스마트 오브젝트**로 만들어, bounding box 위치·크기로 트랜스폼 배치해 z_index 순서로 쌓는다

레이어 PNG는 최종 배치 크기보다 약 2배 고해상도라서, 스마트 오브젝트로 임베드하면 포토샵에서 확대·재배치해도 화질 손실이 없다.

## 사용법

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

## 동작 원리 (요약)

psd-tools는 스마트 오브젝트 *생성*을 공식 지원하지 않는다. 이 도구는 psd-tools의 저수준 직렬화 계층을 이용해 스마트 오브젝트 블록(`SoLd`, `PlLd`, 전역 `lnk2`)을 직접 조립한다. 디스크립터 구조는 Photoshop이 실제로 기록한 바이너리를 base64 템플릿으로 임베드해 두고, uuid·트랜스폼·크기만 런타임에 패치하는 방식이라 견고하다.

또한 psd-tools의 알려지지 않은 버그 — `LinkedLayer` v8 꼬리의 `contentID` 디스크립터를 누락 기록해 **Photoshop이 파일을 아예 열지 못하게 되는 문제** — 를 `LinkedLayerV8` 서브클래스로 우회한다. 상세한 역공학 기록과 인수인계 정보는 [HANDOFF.md](HANDOFF.md) 참조.

## 검증

Photoshop 27.6에서 실제로 열어 8개 레이어 전부 `LayerKind.SMARTOBJECT`로 인식됨을 확인했고, 포토샵이 flatten-export한 PNG(`ps_export.png`)가 기대 썸네일(`final_thumb.png`)과 일치한다. psd-tools 재파싱 검증 스크립트는 `_ref/verify.py`.

## 파일

- `make_psd.py` — 메인 스크립트
- `layer.json` / `final_thumb.png` — 테스트 입력 / 기대 결과
- `_ref/` — 포맷 역공학·검증 스크립트와 참조 PSD (개발·디버깅용, 실행에는 불필요)
- `HANDOFF.md` — 기술 상세·인수인계 문서
