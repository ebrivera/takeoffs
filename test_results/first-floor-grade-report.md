# Pipeline Grade Report

**Overall Score: 0.93** (PASS — threshold 0.70)

## Dimension Scores

| Dimension | Weight | Score |
|-----------|--------|-------|
| building_type | 0.15 | 1.00 |
| structural_system | 0.10 | 1.00 |
| room_completeness | 0.25 | 0.86 |
| room_classification | 0.20 | 0.88 |
| area_reasonableness | 0.15 | 0.95 |
| special_conditions | 0.05 | 1.00 |
| no_hallucinations | 0.10 | 0.95 |

## Reasoning

**building_type**: Correctly identified as RESIDENTIAL, matching ground truth exactly.

**structural_system**: Correctly identified wood frame construction with detailed structural information (2x12 joists at 16" o.c., brick chimney), matching ground truth keywords: wood, frame, timber.

**room_completeness**: Found 8 of 8 expected rooms (Kitchen, Living Room, Dining, WC, Utility, Laundry, Front Porch, Coats/closet). Missing Back Porch mentioned in ground truth, but found 6 core rooms plus 2 additional spaces. Minor deduction for missing back porch.

**room_classification**: Most room types correctly classified (Kitchen, Living Room, WC, Dining, Utility, Laundry, Front Porch). The 'COATS' space is reasonably classified as closet. All major spaces have appropriate functional classifications matching expected use.

**area_reasonableness**: Total area 502.03 SF is within the ±20% tolerance of ground truth 512.0 SF (allowable range: 409.6-614.4 SF). Individual room areas appear physically reasonable for a small farmhouse. Kitchen at 190 SF, Living Room at 122 SF, Dining at 143 SF are all plausible proportions.

**special_conditions**: Excellent detection of special conditions: woodstove, brick chimney, fireplace/chimney, and additional structural details (joists, stairs, corner cupboard, porch railing). All ground truth special conditions identified plus additional relevant features.

**no_hallucinations**: Minor issue: Front Porch and Laundry show 0.0 SF in final space program despite being detected by LLM with estimated areas (48 SF and 12 SF respectively). This suggests a data integration issue rather than hallucination. No phantom rooms or impossible claims detected. Very minor deduction for the area calculation inconsistency.
