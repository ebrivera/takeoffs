# Enhanced Geometry Report: first-floor.pdf

Generated: 2026-02-08 22:38 UTC

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
**Structural system:** Wood frame construction with 2x12 joists at 16" on center, brick chimney indicated

### Room Analysis

| # | Confirmed Label | Type | Notes |
|---|-----------------|------|-------|
| 0 | KITCHEN | KITCHEN | estimated_area_sf: 190, unlabeled in geometry data but clearly identified in text blocks, contains REF notation |
| 1 | LIVING ROOM | LIVING_ROOM | estimated_area_sf: 122, contains woodstove and brick chimney, corner cupboard noted |
| 2 | WC | WC | estimated_area_sf: 18, small water closet/powder room |
| 3 | DINING | DINING | estimated_area_sf: 143 |
| 4 | UTILITY | UTILITY | estimated_area_sf: 9, very small utility space |
| 5 | COATS | CLOSET | estimated_area_sf: 20, coat closet near entry |
| 6 | FRONT PORCH | PORCH | estimated_area_sf: 48, exterior covered porch with railing, stairs indicated with 'UP' notation |
| 7 | LAUNDRY | LAUNDRY | estimated_area_sf: 25, separate laundry room, dimensions approximately 3'-1" x 8' |

### Special Conditions

- Woodstove present in living room
- Brick chimney through structure
- Corner cupboard built-in feature
- Multiple staircases with railings indicated ('UP' notations)
- Stairs with dimensions: 16 risers at 7.5", 3 risers at 7.5"
- 2x12 floor joists at 16" on center structural system
- Front porch with exterior stairs and railing

### Measurement Flags

- Total detected area (502 SF) appears low for a 32' x 16' building footprint which should yield approximately 512 SF
- Utility room at 8.9 SF is extremely small - verify if this is a closet or mechanical space
- Kitchen area (190 SF) seems large relative to other rooms - verify room boundaries
- Missing area likely accounts for wall thicknesses and stair volumes

**Confidence notes:** High confidence in room identification. All major spaces accounted for including kitchen, living room, dining, WC, utility, coats closet, laundry, and front porch. Drawing shows clear dimensions (32' x 16' overall), scale is 1/4"=1'-0", and structural details are well documented. This appears to be a first floor plan of a small residential structure. Area estimates based on dimension annotations and overall building footprint.

## Accuracy vs Expected

| Metric | Expected | Actual | Error |
|--------|----------|--------|-------|
| Scale factor | 48 | 48.0 | +0.0% |
| Total area | 512 SF | 502.0 SF | -1.9% |
| Named rooms | >=4 | 5 | - |

