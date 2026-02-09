# Pipeline Grade Report

**Overall Score: 0.91** (PASS — threshold 0.70)

## Dimension Scores

| Dimension | Weight | Score |
|-----------|--------|-------|
| building_type | 0.15 | 1.00 |
| structural_system | 0.10 | 1.00 |
| room_completeness | 0.25 | 0.86 |
| room_classification | 0.20 | 0.88 |
| area_reasonableness | 0.15 | 0.95 |
| special_conditions | 0.05 | 0.75 |
| no_hallucinations | 0.10 | 0.90 |

## Reasoning

**building_type**: Correctly identified as RESIDENTIAL, matching ground truth exactly.

**structural_system**: Correctly identified wood frame construction with specific structural details (2x12 joists @ 16" OC), matching ground truth keywords: wood, frame, timber.

**room_completeness**: Found 6 of 8 expected rooms. Missing Back Porch but correctly identified Front Porch, Kitchen, Living Room, Dining, WC, Utility, Laundry, and added COATS closet. Strong performance with 7/8 core spaces identified (Front Porch found, Back Porch missing).

**room_classification**: Most room types correctly classified. Kitchen correctly identified (though unlabeled in geometry), Living Room, WC, Dining, Utility all correct. COATS appropriately classified as closet. Front Porch and Laundry correctly typed. Minor issue: Kitchen shown as 'unlabeled' in geometry list but correctly identified by LLM.

**area_reasonableness**: Total area 502 SF is within ±2% of ground truth 512 SF (±20% tolerance). Individual room areas are physically reasonable. Front Porch and Laundry show 0.0 SF in final space program, likely exterior/secondary spaces not captured in polygon geometry, which is acceptable.

**special_conditions**: Identified 3 of 4 main special conditions: woodstove (correctly placed in dining area), brick chimney, and structural system details. Missing explicit mention of hardwood flooring. Also identified additional relevant features like corner cupboard, railings, and stairways.

**no_hallucinations**: Minor issue: Front Porch and Laundry listed with 0.0 SF in final space program suggests these were identified in text but not properly bounded geometrically. This is a data completeness issue rather than hallucination. No phantom rooms or impossible claims, but the 0.0 SF entries are inconsistent with LLM estimates (60 SF and 25 SF respectively).
