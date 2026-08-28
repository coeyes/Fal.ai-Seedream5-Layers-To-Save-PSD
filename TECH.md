# TECH — Creating embedded Smart Object PSDs in pure Python

*Read this in other languages: [한국어](TECH.ko.md)*

Notes on generating a PSD with **embedded Smart Object layers** that Photoshop recognizes as fully valid — in Python only, with no Photoshop installation. Based on psd-tools 1.18; `make_psd.py` in this repository is the working implementation.

## 1. The problem

psd-tools' high-level API only supports *reading* Smart Objects, not creating or editing them. The alternatives are not great either:

| Approach | Limitation |
|---|---|
| pytoshop | Raster layers only |
| Aspose.PSD | Commercial; evaluation watermark |
| ag-psd (TypeScript) | Supports writing, but requires a Node stack |
| Photoshop COM/JSX | Reliable, but requires Photoshop installed |

However, psd-tools' **low-level layer** (`psd_tools.psd`) fully parses the Smart Object-related blocks and can re-serialize them byte-for-byte (round-trip). In other words: there is no "create it for me" API, but if you assemble the structures yourself, the library handles serialization.

## 2. The binary structure of a PSD Smart Object

A Smart Object layer = a regular raster layer + three tagged blocks.

### 2.1 Per-layer tagged blocks

**`SoLd`** (`Tag.SMART_OBJECT_LAYER_DATA1`, kind=`soLD`, version=4) — contains a single Descriptor. Key entries:

| Key | Type | Value |
|---|---|---|
| `Idnt` | String | UUID matching the global `lnk2` item, + `'\x00'` |
| `placed` | String | Placement-instance UUID + `'\x00'` |
| `Trnf`, `nonAffineTransform` | List[8×Double] | Placement corners in **TL→TR→BR→BL** order: `[x1,y1, x2,y1, x2,y2, x1,y2]` |
| `Sz  ` | Descriptor(`Pnt `) | Original content size `Wdth`/`Hght` |
| `warp` | Descriptor(`warp`) | warpNone, `bounds`=classFloatRect(0,0,srcH,srcW) |
| others | | `Annt`=16, `Type`=2, `Rslt`=72 (UnitFloat `#Rsl`), PgNm/totalPages/Crop/frameStep/duration/frameCount, comp=-1, ClMg |

**`PlLd`** (`Tag.PLACED_LAYER2`, kind=`plcL`, version=3) — legacy-compatibility block. uuid (bytes), transform (8 doubles, same corners as SoLd), anti_alias=16, layer_type=RASTER(2), warp (DescriptorBlock2).

The layer's raster channels hold the **placement preview** (the source image resized to its placed size). Photoshop renders this preview as-is when opening the file, so the preview *is* what you see.

### 2.2 Global tagged block: `lnk2`

`Tag.LINKED_LAYER2` in `LayerAndMaskInformation.tagged_blocks`. Each item (`LinkedLayer`) is one embedded file:

- kind=`liFD` (DATA), version=8
- uuid (pascal string) — matches the layer's `SoLd.Idnt`
- filename (unicode, including the null terminator), filetype=`b'png '`
- **data = the original file bytes, verbatim** (a PNG stays a PNG)
- open_file = DescriptorBlock `{compInfo: {compID: -1, originalCompID: -1}}`
- child_id=`'\x00'`, mod_time=0.0, lock_state=0
- **a trailing `{contentID: <uuid>}` DescriptorBlock** ← the trap in §4

Note: in PSD (v1) the `lnk2` block's length field is 4 bytes (8 bytes only in PSB).

## 3. Implementation strategy

### 3.1 Don't hand-build the descriptors — patch a template

The SoLd descriptor is unforgiving: get one field type (UnitFloat units, Enumerated typeIDs), ordering, or naming convention (`'\x00'` terminators) wrong and Photoshop may reject the file. The safe approach:

1. Use Photoshop once (at development time) to create a reference PSD containing a single Smart Object
2. Extract the `SoLd`/`PlLd`/`open_file`/`contentID` block bytes with psd-tools and **embed them as base64 constants in the code**
3. At runtime, parse the template with `SmartObjectLayerData.read()` and patch only the UUIDs, `Trnf`, `Sz  `, and warp bounds

The final script needs no Photoshop at all.

### 3.2 Use psd-tools 1.18's new APIs for the raster part

- Create the document with `PSDImage.new('RGB', size)`. Per-layer transparency channels (-1) are standard even in RGB documents.
- `PixelLayer._build_layer_record_and_channels(rgba_image, name, left, top, Compression.RLE)` — **passing an RGBA image stores the alpha as the TRANSPARENCY_MASK (-1) channel.** The public `PixelLayer.frompil()` is unsuitable here: on RGB documents it converts the alpha into a layer mask instead.
- `psd.append(PixelLayer(psd, record, channels))` — append order is bottom→top.
- `psd.save()` automatically recomputes channel lengths and refreshes the composite preview (ImageData).
- Unicode layer names: `record.tagged_blocks.set_data(Tag.UNICODE_LAYER_NAME, name)`.

## 4. ★ psd-tools bug: missing LinkedLayer v8 `contentID`

**Symptom**: Photoshop refuses to open the generated PSD at all — *"the file is not compatible with this version of Photoshop"*.

**Reproduction**: take a PSD created by Photoshop (containing a Smart Object), read it with psd-tools, and **re-save it without any modification** — Photoshop rejects it the same way. So the bug is in the library's write path.

**Cause**: `LinkedLayer` version 8 carries a `{contentID: <uuid>}` DescriptorBlock (~117 bytes) after the standard fields (lock_state), which psd-tools' `LinkedLayer.read` never parses. Reading still succeeds because each item sits inside a length block (the unread tail is silently discarded), but **on re-write the tail is lost** and Photoshop's lnk2 v8 parser fails.

**Workaround**: subclass `LinkedLayer` and override `write()` to append the contentID DescriptorBlock:

```python
class LinkedLayerV8(LinkedLayer):
    def write(self, fp, padding=1, **kwargs):
        written = super().write(fp, padding=1, **kwargs)
        blk = DescriptorBlock.read(io.BytesIO(CONTENT_ID_TEMPLATE))
        blk[b'contentID'] = String(value=str(uuid.uuid4()) + '\x00')
        return written + blk.write(fp, padding=1)
```

How it was tracked down with binary diffing: compared per-section lengths of the original vs. the re-saved file to confirm the 116-byte loss was entirely inside the `lnk2` block → manually parsed the item's fields to isolate a 117-byte unconsumed tail → identified the `contentID` descriptor in the hexdump.

## 5. Verification methodology

Three stages; for a hand-assembled format the last one is mandatory:

1. **psd-tools re-parse** — does the high-level API classify the layers as `SmartObjectLayer`, and do the embedded bytes match the originals?
2. **Pixel comparison** — diff `psd.composite()` against the expected image
3. **Open it in real Photoshop** — psd-tools is lenient, so passing 1 and 2 does not guarantee Photoshop accepts the file (§4 is exactly such a case). When automating via COM/JSX, set `app.displayDialogs = DialogModes.NO` first — otherwise errors surface as modal dialogs, and COM calls hang forever with `RPC_E_SERVERCALL_RETRYLATER`.

## 6. Limitations

- Only axis-aligned placement (translate/scale) is implemented. `Trnf` accepts arbitrary quad corners, so rotation/shear are possible format-wise.
- Embedded (liFD) only. Externally linked files (liFE) use a different structure.
- Templates were captured from Photoshop 27.x output. If a future version adds fields, re-extract from a fresh reference PSD.
