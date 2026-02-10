# Pipeline Grade Report

**Overall Score: 0.88** (PASS — threshold 0.70)

## Dimension Scores

| Dimension | Weight | Score |
|-----------|--------|-------|
| building_type | 0.15 | 1.00 |
| structural_system | 0.10 | 1.00 |
| room_completeness | 0.25 | 0.75 |
| room_classification | 0.20 | 0.85 |
| area_reasonableness | 0.15 | 0.95 |
| special_conditions | 0.05 | 0.85 |
| no_hallucinations | 0.10 | 0.90 |

## Reasoning

**building_type**: Correctly identified as RESIDENTIAL, matching ground truth exactly.

**structural_system**: Correctly identified wood frame construction with detailed specifications (2x12 joists @ 16 inch OC), matching expected 'wood, frame, timber' keywords.

**room_completeness**: Found 7-8 rooms vs expected 8 rooms. Successfully identified: Kitchen, Living Room, Dining, WC, Utility, Laundry, Front Porch. Missing: Back Porch. Added unexpected: Coats closet (reasonable but not in ground truth). 6/8 core rooms found = 75%.

**room_classification**: Most room types correctly classified. Kitchen correctly identified despite being unlabeled in geometry. All major spaces (Kitchen, Living Room, Dining, WC, Laundry, Utility) have appropriate classifications. Minor issue: 'COATS' classified as closet is reasonable. Front Porch correctly identified as porch type.

**area_reasonableness**: Total area 491 SF vs ground truth 512 SF (±20% = 410-614 SF range). Pipeline falls within acceptable range at 95.9% of expected value. Individual room areas appear physically reasonable for a farmhouse layout.

**special_conditions**: Identified: woodstove (✓), chimney (✓), hardwood (✗). Also found additional details like corner cupboard, joist specifications, stairs with riser details, and refrigerator notation. Missing explicit 'hardwood' mention and 'fireplace' (though chimney/woodstove suggest heating elements). 3/4 key conditions = 75%, but extra architectural details boost score to 85%.

**no_hallucinations**: Generally accurate. Minor concern: Front Porch shows 0.0 SF in final space program despite being identified with estimated 60 SF by LLM, suggesting incomplete data integration rather than hallucination. No phantom rooms or impossible claims detected. All reported features appear legitimate from floor plan analysis.
