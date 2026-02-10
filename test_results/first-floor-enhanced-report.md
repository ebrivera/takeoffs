# Enhanced Geometry Report: first-floor.pdf

Generated: 2026-02-10 01:32 UTC

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
| 0 | KITCHEN | KITCHEN | estimated_area_sf: 188. Located adjacent to living room and dining area. REF (refrigerator) noted in text blocks. This appears to be the largest open space on the first floor. |
| 1 | LAUNDRY | LAUNDRY | estimated_area_sf: 50. Confirmed laundry room with stairs indicated (UP notation, 16R @ 7.5" tread). Located near utility areas. |
| 2 | LIVING ROOM | LIVING_ROOM | estimated_area_sf: 72. Contains woodstove and brick chimney. Corner cupboard noted. This is the main living space. |
| 3 | WC | WC | estimated_area_sf: 18. Water closet/powder room. Appropriate size for half bath. |
| 4 | DINING | DINING | estimated_area_sf: 133. Dining area, likely open to kitchen. Largest designated room space. |
| 5 | UTILITY | UTILITY | estimated_area_sf: 9. Small utility closet or mechanical space. |
| 6 | COATS | CLOSET | estimated_area_sf: 20. Coat closet near entry. |
| 7 | FRONT PORCH | PORCH | estimated_area_sf: 80. Covered front porch with railing noted in text blocks. Dimensions approximately 16' x 5' based on visible measurements. |

### Special Conditions

- Woodstove present in living room
- Brick chimney
- Corner cupboard feature
- 2x12 joists @ 16" OC floor framing system
- Multiple staircases noted with UP indicators (16R @ 7.5", 3R @ 7.5")
- Railing on front porch
- Building dimensions 32' x 16' approximately
- Drawing reference A1.7, sheet 1 of series

### Measurement Flags

- Total detected area (491 SF) seems low for a 32' x 16' footprint which should be approximately 512 SF
- Room 0 (Kitchen) at 188.5 SF seems disproportionately large - may include circulation space or be miscalculated
- Multiple small dimension annotations suggest complex room layout that may not be fully captured by geometry engine
- Wall count of 0 indicates geometry detection may have issues with wall recognition

**Confidence notes:** High confidence in room identification from text blocks. Building is a residential single-family home first floor plan with open kitchen/dining/living layout. The 1/4"=1'-0" scale and HIGH measurement confidence for extracted data is good, but the wall count of 0 and low total area calculation suggest the geometry engine had difficulty with this drawing. All major rooms were identified from text blocks. The presence of stairs (UP notations) indicates this is a multi-story residence. Drawing shows typical wood frame construction details.

## Accuracy vs Expected

| Metric | Expected | Actual | Error |
|--------|----------|--------|-------|
| Scale factor | 48 | 48.0 | +0.0% |
| Total area | 512 SF | 491.0 SF | -4.1% |
| Named rooms | >=4 | 6 | - |

