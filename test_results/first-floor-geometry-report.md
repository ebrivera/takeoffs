# Geometry Engine Accuracy Report: first-floor.pdf

Generated: 2026-02-09 19:19 UTC

## Drawing Info

| Field | Value |
|-------|-------|
| Filename | first-floor.pdf |
| Page size | 1224 x 792 pts (17.0 x 11.0 in) |
| Scale detected | 1/4" =1'-0" (factor=48.0) |
| Vector path count | 2230 |
| Line/Rect/Curve/Poly | 2022 / 4 / 204 / 0 |
| Text blocks | 118 |

## Measurement Results

| Metric | Expected | Actual | Error |
|--------|----------|--------|-------|
| Gross area | 512 SF | 502.0 SF | -1.9% |
| Perimeter | ~96 LF | 97.9 LF | +2.0% |
| Wall count | - | 42 (23H, 19V) | - |
| Total wall length | - | 227.5 LF | - |
| Wall thickness | - | 9.4 pts (~6.2" real) | - |

## Text Extraction

**Room labels found** (9/9): LIVING ROOM, KITCHEN, DINING, FRONT PORCH, BACK PORCH, UTILITY, WC, COATS, LAUNDRY
**Dimension strings found**: 21
**Title block fields found** (5/5): SCALE, 1/4, A1.2, 1ST FLOOR, AMERICAN FARMHOUSE

## Confidence Assessment

| Component | Confidence |
|-----------|------------|
| Overall | **HIGH** |
| Scale detection | high |
| Wall detection | high |
| Text extraction | high |

## Scale Detection Path

Method used: Deterministic text normalization/parsing (notation: '1/4" =1\'-0"', confidence: high)

## Known Limitations

| # | Limitation | Severity | Suggested Fix |
|----|-----------|----------|---------------|
| 1 | Convex hull overestimates area for L-shaped or irregular footprints | **moderate** | Use concave hull or alpha-shape from wall endpoints |
| 2 | Porch area included in gross area (no interior/exterior wall distinction) | **moderate** | Classify wall segments by line weight or room-label proximity |
| 3 | Dimension calibration fallback can pick annotation leader lines instead of dimension lines, yielding wrong scale | **minor** | Require minimum line length for calibration candidates |
| 4 | No room-level area breakdown — only gross footprint computed | **moderate** | Implement room segmentation using flood-fill on wall graph |
| 5 | Wall thickness detection depends on parallel pair analysis — fails on single-line wall representations | **minor** | Fall back to stroke-width heuristic for single-line walls |
| 6 | Only works on vector PDFs — scanned/rasterized drawings produce no geometry | **critical** | Integrate OCR + image-based line detection (Hough transform) for raster fallback |
| 7 | Multi-story PDFs not yet supported — only processes first page | **moderate** | Extend pipeline to iterate pages and match floor labels |

## Recommendations

### What to tune
- **Area tolerance**: Current ±25% is generous. Phase 1 target: ±15%. Production target: ±10%.
- **Min wall length** (`_MIN_WALL_LENGTH_PTS=36`): Works well for 1/4" scale. May need adjustment for 1/8" scale drawings.
- **IQR outlier factor** (`_OUTLIER_IQR_FACTOR=3.0`): Effective at removing title block borders. Tighten to 2.5 if false positives appear.

### VLM vs Geometry: division of labor
- **Geometry handles**: Scale detection, gross area, perimeter, wall count/length, wall thickness.
- **VLM handles**: Building type, structural system, story count, story height, exterior wall type, room identification.
- **Hybrid merge** (HybridAnalyzer): Uses geometry for area when confidence is HIGH/MEDIUM, VLM for semantic fields always.

### PDF classes that work well
- Clean CAD exports with vector geometry (AutoCAD, Revit, SketchUp)
- Drawings at 1/4" or 1/8" architectural scales
- Single-page floor plans with title block and dimension annotations

### PDF classes that work poorly
- Scanned/rasterized drawings (no vector data)
- Multi-page document sets (only first page processed)
- Imperial engineering scales (1"=20', 1"=40') — untested
- Drawings without scale notation in title block

