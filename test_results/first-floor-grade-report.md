# Pipeline Grade Report

**Overall Score: 0.86** (PASS — threshold 0.70)

## Dimension Scores

| Dimension | Weight | Score |
|-----------|--------|-------|
| building_type | 0.15 | 1.00 |
| structural_system | 0.10 | 1.00 |
| room_completeness | 0.25 | 0.71 |
| room_classification | 0.20 | 0.88 |
| area_reasonableness | 0.15 | 0.85 |
| special_conditions | 0.05 | 0.75 |
| no_hallucinations | 0.10 | 0.90 |

## Reasoning

**building_type**: Correctly identified as RESIDENTIAL, matching ground truth exactly.

**structural_system**: Correctly identified wood frame construction with detailed joist specifications (2x12 at 16" OC), matching ground truth keywords: wood, frame, timber.

**room_completeness**: Found 7 of 8 expected rooms. Missing Back Porch entirely. Front Porch detected by LLM but with 0 SF area. Kitchen, Living Room, Dining, WC, Utility, Laundry all present. Score: 5.67/8 rooms = 0.71.

**room_classification**: Most rooms correctly classified. Kitchen properly identified (was unlabeled in geometry but LLM corrected it). Minor issue: 'COATS' classified as generic closet rather than recognizing it as a coat closet variant. All major spaces correctly typed. Score: 7/8 = 0.88.

**area_reasonableness**: Total area 491 SF vs ground truth 512 SF (±20%) = 4.1% difference, well within tolerance. Individual room areas reasonable except Living Room noted as 'unusually small' at 72 SF. Kitchen at 188 SF seems large relative to total. Overall proportions acceptable but some imbalance.

**special_conditions**: Identified woodstove, brick chimney, and structural system (joists). Missing explicit mention of 'hardwood' flooring and 'fireplace' (though chimney implies it). Found 3 of 4 key conditions clearly, partial credit for chimney/fireplace overlap. Score: ~0.75.

**no_hallucinations**: No phantom rooms invented. Areas are real measurements from geometry. Front Porch has 0 SF but was genuinely detected in text blocks (not fabricated). 'COATS' closet is a real space. Minor deduction for Front Porch having impossible 0 SF area in final output despite detection. Score: 0.90.
