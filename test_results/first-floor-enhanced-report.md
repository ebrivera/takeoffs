# Enhanced Geometry Report: first-floor.pdf

Generated: 2026-02-10 00:58 UTC

## Pipeline Summary

| Field | Value |
|-------|-------|
| Scale | 1/4" =1'-0" (factor=48.0) |
| Total area | 491.0 SF |
| Polygonize success | True |
| Room count | 7 |
| Wall count | 71 |
| Confidence | high |
| Scale verification | LLM_CONFIRMED |

## Room Breakdown

| # | Label | Area (SF) | Perimeter (LF) |
|---|-------|-----------|----------------|
| 0 | *(unlabeled)* | 188.5 | 55.5 |
| 1 | LAUNDRY | 49.8 | 37.9 |
| 2 | LIVING ROOM | 72.1 | 40.8 |
| 3 | WC | 18.1 | 18.1 |
| 4 | DINING | 133.2 | 48.5 |
| 5 | UTILITY | 9.1 | 12.1 |
| 6 | COATS | 20.2 | 19.5 |

## LLM Interpretation

**Building type:** RESIDENTIAL
**Structural system:** wood frame with 2x12 joists @ 16" OC

### Room Analysis

| # | Confirmed Label | Type | Notes |
|---|-----------------|------|-------|
| 0 | KITCHEN | KITCHEN | estimated_area_sf: 188.5, contains REF (refrigerator), appears to be combined kitchen/dining space based on area |
| 1 | LAUNDRY | LAUNDRY | estimated_area_sf: 49.8 |
| 2 | LIVING ROOM | LIVING_ROOM | estimated_area_sf: 72.1, contains woodstove and brick chimney, corner cupboard noted |
| 3 | WC | WC | estimated_area_sf: 18.1 |
| 4 | DINING | DINING | estimated_area_sf: 133.2 |
| 5 | UTILITY | UTILITY | estimated_area_sf: 9.1 |
| 6 | COATS | CLOSET | estimated_area_sf: 20.2, coat closet |
| 7 | FRONT PORCH | PORCH | estimated_area_sf: not included in total area, exterior covered space with railing and stairs (16 risers @ 7.5" and 3 risers @ 7.5") |

### Special Conditions

- woodstove present in living room
- brick chimney
- corner cupboard in living room
- multiple staircases with UP indicators (16 R @ 7.5" and 3 R @ 7.5")
- front porch with railing
- 2x12 joists @ 16" OC structural framing

### Measurement Flags

- Total detected area (491 SF) seems low for a residential first floor plan with these room dimensions
- Room 0 (kitchen) area of 188.5 SF represents 38% of total, may indicate measurement overlap or detection issue
- Plan shows 32' x 16' overall dimensions suggesting ~512 SF total
- Multiple stair indicators suggest multi-story dwelling, this is first floor only

**Confidence notes:** High confidence in room identifications based on clear text labels. Building appears to be a small residential dwelling (approximately 512 SF first floor based on 32' x 16' dimensions). Wood frame construction with 2x12 floor joists. The total detected area of 491 SF is close to the calculated 512 SF from overall dimensions. All major rooms identified from text blocks. Special features include woodstove with brick chimney and corner cupboard. Multiple staircases indicate access to upper floor(s) or basement.

## Accuracy vs Expected

| Metric | Expected | Actual | Error |
|--------|----------|--------|-------|
| Scale factor | 48 | 48.0 | +0.0% |
| Total area | 512 SF | 491.0 SF | -4.1% |
| Named rooms | >=4 | 6 | - |

