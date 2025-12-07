# Article Suggestion Scoring System - Detailed Math Explanation

## Overview

The system uses a **three-tier scoring system** with both individual thresholds and a combined weighted score. An article must pass **ALL** of these criteria to be suggested:

1. **Combined Score** ≥ 0.60 (weighted average)
2. **Quality Score** ≥ 0.50 (individual threshold)
3. **Semantic Score** ≥ 0.55 (individual threshold)

---

## The Math: Combined Score Calculation

### Formula
```
Combined Score = (Relevance × 0.4) + (Quality × 0.3) + (Semantic × 0.3)
```

### Why These Weights?

- **Relevance (40%)**: Most important - does the article actually match the storyline?
- **Quality (30%)**: Important - is the article well-written and from a good source?
- **Semantic (30%)**: Important - does it semantically relate to the storyline topic?

The 40/30/30 split prioritizes relevance while still requiring decent quality and semantic match.

---

## Individual Score Components

### 1. Relevance Score (0.0 - 1.0)

**How it's calculated:**
- **Keyword matching**: If article matches storyline keywords → default 0.6
- **Semantic matching**: If using RAG/embeddings → calculated similarity (0.0-1.0)
- **Title match boost**: Exact keyword matches in title get higher scores
- **Content match**: Keywords in content contribute to score

**Default value**: 0.6 (when only keyword matching is used)

**Why 0.6 default?**
- Assumes moderate relevance for keyword matches
- Leaves room for better matches (0.7-1.0) and worse matches (0.0-0.5)

### 2. Quality Score (0.0 - 1.0)

**How it's calculated:**
The quality score is a weighted combination of:

```
Quality Score = 
  Content Length Score × 0.15 +
  Readability Score × 0.20 +
  Structure Score × 0.15 +
  Uniqueness Score × 0.15 +
  Completeness Score × 0.15 +
  Language Quality × 0.20
```

**Plus bonuses:**
- **Source reliability**: Reputable sources (Reuters, AP, BBC, etc.) get +0.1
- **Content length**: 
  - > 1000 chars: +0.1
  - > 500 chars: +0.05
- **Engagement metrics**: If available, contributes up to +0.3
- **Sentiment**: Neutral to positive sentiment contributes

**Typical range**: 0.4 - 0.8 for most articles

**Why 0.5 threshold?**
- Filters out very low-quality content (spam, too short, poorly written)
- Allows average-quality articles through
- High-quality articles (0.7+) are preferred

### 3. Semantic Score (0.0 - 1.0)

**How it's calculated:**
- **Embedding similarity**: Uses sentence transformers to compare article content with storyline context
- **Cosine similarity**: Measures how similar the semantic meaning is
- **Query expansion**: Related terms are considered

**Default value**: 0.6 (when embeddings aren't available)

**Why 0.55 threshold?**
- Slightly lower than relevance because semantic matching is harder
- Still requires meaningful semantic connection
- Prevents completely unrelated articles

---

## Probability Analysis: How Likely Is an Article to Pass?

### Scenario 1: Average Article (Most Common)

**Assumptions:**
- Relevance: 0.6 (keyword match)
- Quality: 0.5 (average quality)
- Semantic: 0.6 (default/estimated)

**Combined Score:**
```
(0.6 × 0.4) + (0.5 × 0.3) + (0.6 × 0.3)
= 0.24 + 0.15 + 0.18
= 0.57
```

**Result**: ❌ **FAILS** - Combined score (0.57) < 0.60 threshold

**Why it fails**: Even though all individual scores meet their thresholds, the weighted average is slightly below 0.60.

### Scenario 2: Good Article

**Assumptions:**
- Relevance: 0.7 (strong keyword match)
- Quality: 0.6 (above average)
- Semantic: 0.6 (moderate semantic match)

**Combined Score:**
```
(0.7 × 0.4) + (0.6 × 0.3) + (0.6 × 0.3)
= 0.28 + 0.18 + 0.18
= 0.64
```

**Result**: ✅ **PASSES** - All criteria met:
- Combined: 0.64 ≥ 0.60 ✓
- Quality: 0.6 ≥ 0.5 ✓
- Semantic: 0.6 ≥ 0.55 ✓

### Scenario 3: High-Quality, Low Relevance

**Assumptions:**
- Relevance: 0.5 (weak match)
- Quality: 0.8 (excellent quality)
- Semantic: 0.7 (strong semantic match)

**Combined Score:**
```
(0.5 × 0.4) + (0.8 × 0.3) + (0.7 × 0.3)
= 0.20 + 0.24 + 0.21
= 0.65
```

**Result**: ❌ **FAILS** - Combined score passes, but:
- Combined: 0.65 ≥ 0.60 ✓
- Quality: 0.8 ≥ 0.5 ✓
- Semantic: 0.7 ≥ 0.55 ✓
- **BUT**: Relevance 0.5 < 0.6 (no explicit threshold, but combined score calculation means it's effectively required)

Actually, this would pass! The combined score compensates for lower relevance.

### Scenario 4: Low Quality Article

**Assumptions:**
- Relevance: 0.7 (strong match)
- Quality: 0.4 (poor quality)
- Semantic: 0.6 (moderate)

**Combined Score:**
```
(0.7 × 0.4) + (0.4 × 0.3) + (0.6 × 0.3)
= 0.28 + 0.12 + 0.18
= 0.58
```

**Result**: ❌ **FAILS** - Two reasons:
- Combined: 0.58 < 0.60 ✗
- Quality: 0.4 < 0.5 ✗

---

## Why These Thresholds Were Chosen

### Historical Reasoning (Likely)

1. **Combined Score 0.60**: 
   - Represents "above average" match
   - Filters out marginal matches (0.4-0.59)
   - Allows good matches (0.6-0.8) and excellent matches (0.8-1.0)

2. **Quality Score 0.50**:
   - Filters out spam and very low-quality content
   - Allows average news articles
   - Most reputable sources score 0.5-0.7

3. **Semantic Score 0.55**:
   - Slightly lower than relevance threshold
   - Acknowledges that semantic matching is harder
   - Still requires meaningful connection

### The Problem: They're Too Strict Together

**The issue**: When all three thresholds are applied simultaneously, the probability of passing is quite low:

- **Best case** (all scores at threshold): Combined = 0.57 → **FAILS**
- **Realistic case** (slightly above thresholds): Combined = 0.60-0.62 → **Barely passes**

**Estimated pass rate**: Only ~20-30% of keyword-matched articles will pass all criteria.

---

## Recommended Adjustments

### Option 1: Lower Combined Threshold (Easiest)
```
min_relevance_score: 0.55  (was 0.60)
```
This allows articles with:
- Relevance: 0.6, Quality: 0.5, Semantic: 0.55 → Combined: 0.57 → **PASSES**

### Option 2: Lower Individual Thresholds
```
min_quality_score: 0.45  (was 0.50)
min_semantic_score: 0.50  (was 0.55)
```
This allows more articles through while still filtering very poor matches.

### Option 3: Adjust Weighting (More Complex)
Change the formula to:
```
Combined = (Relevance × 0.5) + (Quality × 0.25) + (Semantic × 0.25)
```
This prioritizes relevance more, which makes sense for article suggestions.

### Option 4: Use "OR" Logic for Edge Cases
Allow articles that pass 2 out of 3 individual thresholds if combined score is high enough.

---

## Real-World Example

**20 articles found, 0 suggested** - Why?

Most articles likely have:
- Relevance: 0.6 (keyword match)
- Quality: 0.4-0.5 (average to below average)
- Semantic: 0.5-0.6 (estimated/default)

**Combined scores**: 0.54 - 0.58

**Result**: All fail the 0.60 combined threshold, even though they might be relevant!

---

## Conclusion

The thresholds are **conservative** and designed to prevent false positives, but they may be **too strict** for practical use. The system is finding relevant articles (20 found) but filtering them all out due to the strict combined score requirement.

**Recommendation**: Lower `min_relevance_score` to **0.50-0.55** to see more suggestions while still maintaining quality standards.


