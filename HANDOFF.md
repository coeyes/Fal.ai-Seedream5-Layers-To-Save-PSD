# HANDOFF — seedream5_layer

다른 에이전트/개발자가 이 프로젝트를 이어받아 작업할 수 있도록, 조사 과정에서 알아낸 사실과 구현 내용을 전부 정리한 문서다. 2026-08-24 기준.

## 1. 목표와 달성 상태

**목표**: seedream5pro layerize 결과 JSON(`layer.json`)을 입력받아, 각 레이어 PNG를 다운로드해 **임베디드 스마트 오브젝트**로 쌓은 PSD를 생성하는 스크립트. **Photoshop 설치 없이 순수 Python으로.**

**상태: 완료·검증됨.** `make_psd.py`가 `output.psd`를 생성하고, Photoshop 27.6이 정상적으로 열어 8개 레이어 전부를 `LayerKind.SMARTOBJECT`로 인식한다. 포토샵이 직접 flatten-export한 PNG(`ps_export.png`)가 기대 썸네일(`final_thumb.png`)과 일치한다.

```
python make_psd.py layer.json [-o output.psd]
```

## 2. 입력 JSON 구조 (seedream5pro layerize)

```jsonc
{ "layers": [ {
    "image": { "url": "...png", "file_name": "...", ... },
    "z_index": 0,            // 0부터 위로 쌓임. 0 = 배경
    "bounding_box": {        // z_index 0은 null
      "absolute":   [x1, y1, x2, y2],   // 배경 픽셀 좌표계
      "normalized": [0..999 스케일]
    },
    "name": "Perfume bottle" // z_index 0은 null → "background"로 명명
} ] }
```

핵심 사실:
- **z_index 0 (배경)이 캔버스 크기의 기준.** 테스트 데이터에선 866×1152 RGB.
- **레이어 PNG는 캔버스 크기도 bbox 크기도 아닌 고해상도 원본이다.** 예: bbox 866×190짜리 레이어의 PNG가 1664×366 (약 1.92배). 그래서 스마트 오브젝트가 적합하다 — 원본을 그대로 임베드하고 트랜스폼으로 bbox에 축소 배치.
- `bounding_box.absolute`는 `[x1, y1, x2, y2]` (left, top, right, bottom).

## 3. 핵심 발견: psd-tools로 스마트 오브젝트 PSD 만들기

### 3.1 라이브러리 지형

- **psd-tools 1.18 고수준 API는 스마트 오브젝트 생성/편집 미지원.** 단, 저수준 `psd_tools.psd` 계층은 관련 블록을 완전히 파싱·재직렬화(라운드트립)할 수 있다 → 구조체를 직접 조립하면 생성 가능.
- psd-tools 1.18에 **`PixelLayer.frompil()` 등 고수준 레이어 생성 API가 새로 생겼다** (구버전엔 없음). 래스터 부분은 이걸 활용.
- 대안 검토: `pytoshop`(래스터만), `Aspose.PSD`(유료·워터마크), `ag-psd`(TypeScript, 스마트 오브젝트 쓰기 지원 — Python이 안 되면 이게 차선책), Photoshop COM(가장 확실하지만 포토샵 필요).

### 3.2 PSD 스마트 오브젝트의 바이너리 구조

Photoshop이 만든 참조 PSD를 psd-tools로 덤프해 확인한 구조:

**레이어 레코드의 tagged blocks** (일반 래스터 레이어 블록에 추가로):
- `Tag.PLACED_LAYER2` (`PlLd`) — `PlacedLayerData`: kind=`plcL`, version=3, uuid(bytes), page=1, total_pages=1, anti_alias=16, layer_type=RASTER(2), transform(8 doubles), warp(DescriptorBlock2)
- `Tag.SMART_OBJECT_LAYER_DATA1` (`SoLd`) — `SmartObjectLayerData`: kind=`soLD`, version=4, data=Descriptor with keys:
  - `Idnt` (String): lnk2 아이템과 매칭되는 uuid + `'\x00'`
  - `placed` (String): 별도 uuid + `'\x00'`
  - `Trnf` / `nonAffineTransform` (List[8 Double]): 배치 코너 **[x1,y1, x2,y1, x2,y2, x1,y2] (TL TR BR BL)**
  - `Sz  ` (Descriptor `Pnt `): 원본 콘텐츠 크기 Wdth/Hght
  - `warp`: warpStyle=warpNone, bounds=classFloatRect(0,0,원본h,원본w), uOrder/vOrder=4
  - 기타: PgNm, totalPages, Crop, frameStep, duration, frameCount, Annt=16, Type=2, Rslt=72(UnitFloat #Rsl), comp/compInfo=-1, ClMg
- 레이어의 래스터 채널 = 배치 결과 프리뷰 (원본을 bbox 크기로 리사이즈한 것, bbox 위치에)

**전역 tagged block** (`LayerAndMaskInformation.tagged_blocks`):
- `Tag.LINKED_LAYER2` (`lnk2`) — `LinkedLayers` 리스트. 각 `LinkedLayer`: kind=DATA(`liFD`), version=8, uuid(pascal str), filename(unicode, `'이름.png\x00'` — 널 종결 포함), filetype=`b'png '`, creator=`b'\x00\x00\x00\x00'`, open_file(DescriptorBlock {compInfo}), **data=PNG 원본 바이트**, child_id=`'\x00'`, mod_time=0.0, lock_state=0
- PSD v1에서 lnk2 블록 길이 필드는 **4바이트**다 (8바이트는 PSB만).

### 3.3 ★ psd-tools 버그: LinkedLayer v8 contentID 누락 (이것 때문에 포토샵이 파일 거부)

**증상**: 생성한 PSD를 포토샵이 "파일이 이 버전과 호환되지 않는다"며 열기 거부.

**원인 규명 과정**: 포토샵제 참조 PSD를 psd-tools로 **읽고 그대로 재저장만 해도 동일하게 거부**됨 → 내 조립이 아니라 라이브러리 쓰기 버그. 바이너리 diff로 116바이트 손실이 전부 `lnk2` 블록 안임을 확인.

**원인**: `LinkedLayer` version 8의 꼬리에는 `{contentID: <uuid>}` DescriptorBlock(~117B)이 붙는데, psd-tools의 `LinkedLayer.read`가 이를 파싱하지 않아(길이 블록 안 잔여 바이트로 버려짐) 재작성 시 누락된다. **이 필드가 없으면 Photoshop이 lnk2 v8 파싱에 실패해 파일 전체를 거부한다.**

**해결**: `LinkedLayer` 서브클래스(`LinkedLayerV8`)에서 `write()` 오버라이드 — super 기록 후 contentID DescriptorBlock 바이트를 덧붙임. (업스트림 이슈 제보 가치 있음.)

### 3.4 구현 전략: 템플릿 임베드 + 런타임 패치

SoLd 디스크립터를 필드별로 손으로 조립하면 타입/순서/이름 관례(`'\x00'` 종결 등)를 틀리기 쉽다. 대신:

1. **개발 시 1회** Photoshop COM으로 참조 PSD 생성 (`_ref/reference.psd` — z0.png 열고 z7.png를 Place)
2. psd-tools로 `SoLd`·`PlLd`·`open_file`·`contentID` 블록 바이트를 추출해 **base64 템플릿으로 스크립트에 상수 임베드**
3. 런타임엔 템플릿을 `read()`로 파싱한 뒤 uuid·Trnf·Sz·warp bounds만 패치

→ 최종 스크립트는 포토샵 완전 불필요. 템플릿 재추출이 필요하면 `_ref/extract_templates.py` 참고.

### 3.5 래스터 레이어 조립 (psd-tools 활용 포인트)

- `PSDImage.new('RGB', canvas)` → 캔버스. RGB 문서에 레이어별 투명 채널(-1)은 표준이며 포토샵 OK.
- `PixelLayer._build_layer_record_and_channels(RGBA이미지, name, left, top, Compression.RLE)` — **RGBA를 직접 넘기면 알파가 TRANSPARENCY_MASK(-1) 채널로 들어간다.** 공개 API `PixelLayer.frompil()`을 쓰면 RGB 문서에선 알파를 레이어 마스크로 바꿔버리므로 쓰지 않았다.
- `psd.append(PixelLayer(psd, record, channels))` — 추가 순서 = 아래→위 (z_index 오름차순으로 append).
- `psd.save()`가 채널 길이 재계산(`_update_channel_length`)과 합성 프리뷰(ImageData) 갱신을 자동으로 한다. 직접 계산 불필요.
- 유니코드 레이어명: `record.tagged_blocks.set_data(Tag.UNICODE_LAYER_NAME, name)` + `Tag.LAYER_ID`.

## 4. 검증 방법 (재검증 시 그대로 따라하면 됨)

1. `python _ref/verify.py` — psd_tools로 output.psd 재파싱: 레이어가 `SmartObjectLayer`인지, 임베디드 PNG 바이트 크기가 원본과 같은지, `composite()` → `verify.png`
2. `python _ref/diff.py` — `verify.png` vs `final_thumb.png` 픽셀 diff (평균 8.7/255 수준이면 정상 — 썸네일 리샘플·워터마크 차이)
3. **Photoshop COM 실개방** (결정적 검증):
   ```powershell
   $ps = New-Object -ComObject Photoshop.Application
   $ps.DoJavaScript(@'
   app.displayDialogs = DialogModes.NO;   // ★ 필수, 아래 함정 참조
   var doc = app.open(new File("D:/proj/seedream5_layer/output.psd"));
   // doc.artLayers[i].kind == LayerKind.SMARTOBJECT 확인, PNG export, close
   '@)
   ```

### COM 자동화 함정

- **`app.displayDialogs = DialogModes.NO`를 JSX 첫 줄에 반드시 넣어라.** 안 넣으면 열기 실패 시 에러가 **모달 대화상자**로 떠서 DoJavaScript가 영원히 안 돌아오고, 이후 모든 COM 호출이 `RPC_E_SERVERCALL_RETRYLATER`(0x8001010A)로 실패한다. 이 상태에 빠지면 대화상자의 OK를 (UIA 등으로) 눌러야 풀린다.
- PowerShell 5에서 `-c`로 인라인 파이썬을 넘기면 내부 큰따옴표가 깨진다. 파이썬 코드는 파일로 저장해 실행할 것.

## 5. 파일 목록

| 파일 | 설명 |
|---|---|
| `make_psd.py` | **본체.** JSON → 스마트 오브젝트 PSD. 포토샵 불필요 |
| `requirements.txt` | psd-tools, pillow |
| `layer.json` | 테스트 입력 (seedream5pro layerize 결과, 8 레이어) |
| `final_thumb.png` | 기대 결과 썸네일 (검증 기준) |
| `output.psd` | 생성 결과 (17MB, 검증 통과) |
| `verify.png` | psd-tools composite 검증 출력 |
| `ps_export.png` | 포토샵이 직접 flatten-export한 검증 출력 |
| `_ref/reference.psd` | 포토샵제 참조 PSD (역공학 원본) |
| `_ref/extract_templates.py` | 참조 PSD → base64 템플릿 추출 |
| `_ref/dump.py`, `dump2.py` | 블록 구조 덤프 (역공학 기록) |
| `_ref/verify.py`, `diff.py` | 검증 스크립트 |
| `_ref/roundtrip.py`, `bindiff.py`, `secdiff.py`, `tail.py` | contentID 버그 규명에 쓴 스크립트들 |

환경: Windows 11, Python 3.12, `uv venv --seed`로 만든 `.venv` (psd-tools 1.18.0, pillow 12.3.0, numpy). 실행 전 `.venv\Scripts\activate`.

## 6. 남은 것 / 확장 시 참고

- 회전·왜곡 트랜스폼은 미지원 (입력 JSON이 축정렬 bbox만 주므로 불필요했음). 필요해지면 `Trnf` 코너 8개에 회전 좌표를 넣으면 된다 — 포맷 자체는 지원.
- ~~파일명 정제 미처리~~ → 처리됨: `safe_filename()`이 금지 문자 `_` 치환 + Windows 예약어 회피 + 대소문자 무시 중복 접미사(`_2`...)를 수행한다. z0의 `background`가 이름을 선점하므로 이후 `Background` 레이어는 `Background_2`가 된다. PSD 레이어 표시명은 원본 그대로, LinkedLayer filename과 `--gen-layers-folder`(기본 1) 출력 파일명(`<zindex>_<fname>.png`)에만 정제명 사용. 단위 검증: `_ref/test_safe_filename.py`.
- psd-tools 업스트림에 contentID 버그 이슈 제보 후보. 버전 업 시 `LinkedLayerV8` 우회가 불필요해질 수 있으니 재현 스크립트는 `_ref/roundtrip.py`.
