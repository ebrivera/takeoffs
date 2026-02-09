# Enhanced Geometry Report: first-floor.pdf

Generated: 2026-02-09 19:19 UTC

## Pipeline Summary

| Field | Value |
|-------|-------|
| Scale | 1/4" =1'-0" (factor=48.0) |
| Total area | 502.0 SF |
| Polygonize success | True |
| Room count | 6 |
| Wall count | 42 |
| Confidence | high |
| Scale verification | LLM_CONFIRMED |

## Room Breakdown

| # | Label | Area (SF) | Perimeter (LF) |
|---|-------|-----------|----------------|
| 0 | *(unlabeled)* | 190.2 | 55.7 |
| 1 | LIVING ROOM | 121.6 | 47.0 |
| 2 | WC | 18.4 | 18.3 |
| 3 | DINING | 142.9 | 49.7 |
| 4 | UTILITY | 8.9 | 11.9 |
| 5 | COATS | 20.1 | 19.4 |

## LLM Interpretation

**Building type:** RESIDENTIAL
**Structural system:** wood frame with 2x12 joists @ 16" OC

### Room Analysis

| # | Confirmed Label | Type | Notes |
|---|-----------------|------|-------|
| 0 | KITCHEN | KITCHEN | estimated_area_sf: 190; appears to be combined KITCHEN area based on text blocks; includes REF notation |
| 1 | LIVING ROOM | LIVING_ROOM | estimated_area_sf: 122; detected area matches extraction; includes woodstove and brick chimney |
| 2 | WC | WC | estimated_area_sf: 18; water closet/half bath |
| 3 | DINING | DINING | estimated_area_sf: 143; detected area matches extraction |
| 4 | UTILITY | UTILITY | estimated_area_sf: 9; small utility closet or space |
| 5 | COATS | CLOSET | estimated_area_sf: 20; coat closet |
| 6 | FRONT PORCH | PORCH | estimated_area_sf: 48; covered front porch with railing; based on 6'-6" + 5'-6" + 3'-4" dimensions visible; porch appears to be 32' wide x variable depth |
| 7 | LAUNDRY | LAUNDRY | estimated_area_sf: 24; separate laundry room identified in text blocks; dimensions approximately 8" + 3'-1" + 8" width |

### Special Conditions

- Woodstove present in living room
- Brick chimney
- Corner cupboard in living area
- Staircase with 16 risers @ 7.5" indicated with UP notation
- Additional stair with 3 risers @ 7.5"
- Railing on front porch
- Floor framing: 2x12 joists @ 16" OC
- Building dimensions: 32' x 16' primary footprint

### Measurement Flags

- Total detected area (502 SF) appears lower than expected for 32' x 16' footprint (512 SF) - likely porch area not fully counted
- Room 0 (Kitchen) labeled as unlabeled in extraction but clearly marked KITCHEN in text blocks
- Front porch area not detected as separate room by geometry engine
- Laundry room not detected by geometry engine but clearly labeled in text blocks

**Confidence notes:** HIGH confidence in room identification based on clear text labels. Building is a small residential single-family dwelling, first floor plan only. Total living area approximately 502 SF with additional porch area. Wood frame construction with conventional joist framing. All major rooms identified from text blocks including Kitchen, Living Room, Dining, WC, Utility, Coats closet, Front Porch, and Laundry.

## Accuracy vs Expected

| Metric | Expected | Actual | Error |
|--------|----------|--------|-------|
| Scale factor | 48 | 48.0 | +0.0% |
| Total area | 512 SF | 502.0 SF | -1.9% |
| Named rooms | >=4 | 5 | - |

