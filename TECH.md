# TECH — 순수 Python으로 임베디드 스마트 오브젝트 PSD 생성하기

Photoshop 없이 Python만으로, Photoshop이 정상 인식하는 **임베디드 스마트 오브젝트 레이어 PSD**를 생성하는 기법 정리다. psd-tools 1.18 기준이며, 이 저장소의 `make_psd.py`가 실제 구현체다.

## 1. 문제

psd-tools의 고수준 API는 스마트 오브젝트를 *읽기*만 지원하고 생성·편집은 미지원이다. 다른 선택지도 마땅치 않다:

| 방법 | 한계 |
|---|---|
| pytoshop | 래스터 레이어만 |
| Aspose.PSD | 상용, 평가판 워터마크 |
| ag-psd (TypeScript) | 쓰기 지원하나 Node 스택 필요 |
| Photoshop COM/JSX | 확실하지만 Photoshop 설치 필수 |

그러나 psd-tools의 **저수준 계층**(`psd_tools.psd`)은 스마트 오브젝트 관련 블록을 완전히 파싱하고 바이트로 재직렬화(라운드트립)할 수 있다. 즉 "만들어주는 API"는 없지만, 구조체를 직접 조립하면 직렬화는 라이브러리가 해준다.

## 2. PSD 스마트 오브젝트의 바이너리 구조

스마트 오브젝트 레이어 = 일반 래스터 레이어 + 태그 블록 3종.

### 2.1 레이어별 태그 블록

**`SoLd`** (`Tag.SMART_OBJECT_LAYER_DATA1`, kind=`soLD`, version=4) — Descriptor 하나를 담는다. 주요 키:

| 키 | 타입 | 값 |
|---|---|---|
| `Idnt` | String | 전역 `lnk2` 아이템과 매칭되는 UUID + `'\x00'` |
| `placed` | String | 배치 인스턴스 UUID + `'\x00'` |
| `Trnf`, `nonAffineTransform` | List[8×Double] | 배치 사각형 코너 **TL→TR→BR→BL** 순 `[x1,y1, x2,y1, x2,y2, x1,y2]` |
| `Sz  ` | Descriptor(`Pnt `) | 원본 콘텐츠 크기 `Wdth`/`Hght` |
| `warp` | Descriptor(`warp`) | warpNone, `bounds`=classFloatRect(0,0,원본h,원본w) |
| 기타 | | `Annt`=16, `Type`=2, `Rslt`=72(UnitFloat `#Rsl`), PgNm/totalPages/Crop/frameStep/duration/frameCount, comp=-1, ClMg |

**`PlLd`** (`Tag.PLACED_LAYER2`, kind=`plcL`, version=3) — 구버전 호환 블록. uuid(bytes), transform(8 doubles, SoLd와 동일 코너), anti_alias=16, layer_type=RASTER(2), warp(DescriptorBlock2).

레이어의 래스터 채널에는 **배치 결과 프리뷰**(원본을 배치 크기로 리사이즈한 픽셀)를 넣는다. Photoshop은 열 때 이 프리뷰를 그대로 쓰므로, 프리뷰가 곧 눈에 보이는 결과다.

### 2.2 전역 태그 블록: `lnk2`

`LayerAndMaskInformation.tagged_blocks`의 `Tag.LINKED_LAYER2`. 각 아이템(`LinkedLayer`)이 임베디드 파일 하나다:

- kind=`liFD`(DATA), version=8
- uuid(pascal string) — 레이어 `SoLd.Idnt`와 매칭
- filename(unicode, 널 종결 포함), filetype=`b'png '`
- **data = 원본 파일 바이트 통째로** (PNG면 PNG 그대로)
- open_file = DescriptorBlock `{compInfo: {compID: -1, originalCompID: -1}}`
- child_id=`'\x00'`, mod_time=0.0, lock_state=0
- **꼬리에 `{contentID: <uuid>}` DescriptorBlock** ← §4의 함정

참고: PSD(v1)에서 `lnk2` 블록의 길이 필드는 4바이트다 (8바이트는 PSB에서만).

## 3. 구현 전략

### 3.1 디스크립터는 손으로 짓지 말고 템플릿을 패치하라

SoLd 디스크립터는 필드 타입(UnitFloat 단위, Enumerated typeID 등)·순서·이름 관례(`'\x00'` 종결)를 하나라도 틀리면 Photoshop이 거부할 수 있다. 안전한 방법:

1. Photoshop으로 스마트 오브젝트 1개짜리 참조 PSD를 한 번 만든다 (개발 시 1회)
2. psd-tools로 `SoLd`/`PlLd`/`open_file`/`contentID` 블록 바이트를 추출해 **base64 상수로 코드에 임베드**
3. 런타임엔 `SmartObjectLayerData.read()`로 템플릿을 파싱한 뒤 UUID·`Trnf`·`Sz  `·warp bounds만 패치

최종 실행엔 Photoshop이 전혀 필요 없다.

### 3.2 래스터 부분은 psd-tools 1.18 신규 API 활용

- `PSDImage.new('RGB', size)`로 문서 생성. RGB 문서에서도 레이어별 투명 채널(-1)은 표준이다.
- `PixelLayer._build_layer_record_and_channels(rgba_image, name, left, top, Compression.RLE)` — **RGBA 이미지를 넘기면 알파가 TRANSPARENCY_MASK(-1) 채널로 들어간다.** 공개 API `PixelLayer.frompil()`은 RGB 문서에서 알파를 레이어 마스크로 변환해버리므로 부적합.
- `psd.append(PixelLayer(psd, record, channels))` — append 순서가 아래→위.
- `psd.save()`가 채널 길이 재계산과 합성 프리뷰(ImageData) 갱신을 자동 수행한다.
- 유니코드 레이어명: `record.tagged_blocks.set_data(Tag.UNICODE_LAYER_NAME, name)`.

## 4. ★ psd-tools 버그: LinkedLayer v8 `contentID` 누락

**증상**: 생성한 PSD를 Photoshop이 *"파일이 이 버전의 Photoshop과 호환되지 않습니다"* 라며 열기 자체를 거부한다.

**재현**: Photoshop이 만든 (스마트 오브젝트 포함) PSD를 psd-tools로 읽고 **수정 없이 재저장만 해도** 동일하게 거부된다. 즉 라이브러리 쓰기 경로의 버그다.

**원인**: `LinkedLayer` version 8은 표준 필드(lock_state) 뒤에 `{contentID: <uuid>}` DescriptorBlock(~117B)이 붙는데, psd-tools의 `LinkedLayer.read`는 이를 파싱하지 않는다. 각 아이템이 길이 블록 안에 있어 읽기는 문제없이 넘어가지만(잔여 바이트 폐기), **재작성 시 이 꼬리가 누락**되고 Photoshop의 lnk2 v8 파서가 실패한다.

**우회**: `LinkedLayer` 서브클래스에서 `write()`를 오버라이드해 contentID DescriptorBlock 바이트를 덧붙인다:

```python
class LinkedLayerV8(LinkedLayer):
    def write(self, fp, padding=1, **kwargs):
        written = super().write(fp, padding=1, **kwargs)
        blk = DescriptorBlock.read(io.BytesIO(CONTENT_ID_TEMPLATE))
        blk[b'contentID'] = String(value=str(uuid.uuid4()) + '\x00')
        return written + blk.write(fp, padding=1)
```

바이너리 diff로 찾는 과정: 원본 vs 재저장본의 섹션별 길이를 비교해 116바이트 손실이 전부 `lnk2` 블록 안임을 확인 → 아이템 필드를 수동 파싱해 소비되지 않은 꼬리 117바이트를 특정 → hexdump에서 `contentID` 디스크립터 확인.

## 5. 검증 방법론

3단계로 검증했다. 손으로 조립한 포맷은 마지막 단계가 필수다:

1. **psd-tools 재파싱** — 고수준 API가 레이어를 `SmartObjectLayer`로 분류하는지, 임베디드 바이트가 원본과 일치하는지
2. **픽셀 비교** — `psd.composite()` 결과를 기대 이미지와 diff
3. **실제 Photoshop으로 열기** — psd-tools는 관대해서 1·2를 통과해도 Photoshop이 거부할 수 있다 (§4가 정확히 그 사례). COM/JSX 자동화 시 `app.displayDialogs = DialogModes.NO`를 반드시 먼저 설정할 것 — 안 하면 오류가 모달로 떠서 COM 호출이 `RPC_E_SERVERCALL_RETRYLATER`로 무한 대기한다.

## 6. 한계

- 축정렬 배치(이동·스케일)만 구현했다. `Trnf`가 임의 사각형 코너를 받으므로 회전·시어도 포맷상 가능하다.
- 임베디드(liFD)만 다룬다. 외부 링크 파일(liFE)은 별도 구조.
- 템플릿은 Photoshop 27.x 출력 기준. 훗날 버전에서 필드가 추가되면 참조 PSD를 다시 추출하면 된다.
