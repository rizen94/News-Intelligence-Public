# Topic → Storyline Assignment: Investigation & Fix

## Problem
The "South American Burglary Ring" storyline contained 20 articles, but only 1–2 were actually about that story. Unrelated articles (Hezbollah, Hong Kong campsites, Trump/Freedom, etc.) were incorrectly included.

## Flow Summary

### 1. Topic Extraction (per article)
- **LLMTopicExtractor** processes each article independently
- For each article: `_extract_topics_from_single_article(article_id, title, content, summary)`
- Two sources of topics:
  - **Entity extraction** (NER): Persons, orgs, locations → added as topics
  - **LLM** (TopicClusteringService): Sends title + content (2000 chars) to Ollama, asks for 2–5 main topics
- Returns list of `TopicInsight` with `name`, `articles=[article_id]`, `relevance_score`, `keywords`

### 2. Topic Merging
- `_merge_and_rank_topics()` merges topics by **exact name match** (lowercase)
- If Article A and Article B both produce "South American Burglary Ring", they merge into one topic with `articles=[A,B]`
- **Root cause**: The LLM is returning "South American Burglary Ring" for unrelated articles

### 3. Saving to DB
- `save_topics_to_database(topics)` in advanced_topic_extractor
- For each (topic_name, article_id): inserts into `article_topic_clusters`
- No validation that the article actually discusses the topic

### 4. Convert to Storyline
- `convert_to_storyline` fetches ALL articles from `article_topic_clusters` for that topic
- Adds every assigned article to the storyline
- So bad assignments upstream flow directly into storylines

## Root Causes

1. **LLM over-extraction**: Ollama returns topics not clearly present in the article
   - Digest articles ("TAC Right Now: AOC, Trump, Iran...") may trigger extraction of sidebar topics
   - Model may hallucinate or latch onto tangentially related terms
   - Prompt is permissive ("2–5 main topics")

2. **No relevance gate**: Low-confidence assignments (e.g. 0.4) are still saved

3. **No article–topic validation**: Nothing checks that the article text actually mentions the topic

## Fixes Implemented

### 1. Stricter LLM Prompt (topic_clustering_service.py)
- System prompt: "Only extract topics that are EXPLICITLY discussed in this specific article. Do not include topics from other news. Each topic must be clearly mentioned in the article text. Never infer or hallucinate topics."
- Instruction 2: "Do NOT include topics from other news stories, sidebars, or tangentially related events not in this article"

### 2. Article–Topic Relevance Validation (llm_topic_extractor.py)
- New `_article_mentions_topic(article_text, topic_name, keywords)` before adding LLM topics
- For multi-word topics (3+ words): require at least 2 significant words from the topic/keywords to appear in the article
- For shorter topics: require 1 match
- Filters generic words (the, and, news, etc.)
- Prevents assignments like Hezbollah → "South American Burglary Ring"
