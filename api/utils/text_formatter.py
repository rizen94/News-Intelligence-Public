"""
News Intelligence System v3.0 - Text Formatting Utility
Improves readability of articles and storylines with proper formatting
"""

import re


def format_article_content(content: str) -> str:
    """Format article content for better readability"""
    if not content:
        return content
    
    # Clean up the content
    formatted = content.strip()
    
    # Split into paragraphs
    paragraphs = re.split(r'\n\s*\n', formatted)
    
    # Process each paragraph
    formatted_paragraphs = []
    for paragraph in paragraphs:
        if paragraph.strip():
            # Clean up paragraph
            paragraph = paragraph.strip()
            
            # Add proper spacing around sentences
            paragraph = re.sub(r'\.([A-Z])', r'. \1', paragraph)
            
            # Add spacing around common punctuation
            paragraph = re.sub(r'([.!?])([A-Z])', r'\1 \2', paragraph)
            
            # Clean up multiple spaces
            paragraph = re.sub(r'\s+', ' ', paragraph)
            
            # Add paragraph break
            formatted_paragraphs.append(paragraph)
    
    # Join paragraphs with double line breaks
    return '\n\n'.join(formatted_paragraphs)

def format_storyline_summary(summary: str) -> str:
    """Format storyline summary for better readability"""
    if not summary:
        return summary
    
    # Clean up the summary
    formatted = summary.strip()
    
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', formatted)
    
    # Process each sentence
    formatted_sentences = []
    for sentence in sentences:
        if sentence.strip():
            # Clean up sentence
            sentence = sentence.strip()
            
            # Add proper spacing
            sentence = re.sub(r'\s+', ' ', sentence)
            
            # Capitalize first letter
            if sentence and not sentence[0].isupper():
                sentence = sentence[0].upper() + sentence[1:]
            
            formatted_sentences.append(sentence)
    
    # Join sentences with proper spacing
    return '. '.join(formatted_sentences) + ('.' if formatted_sentences and not formatted_sentences[-1].endswith('.') else '')

def format_storyline_timeline(timeline: str) -> str:
    """Format storyline timeline for better readability"""
    if not timeline:
        return timeline
    
    # Clean up the timeline
    formatted = timeline.strip()
    
    # Split into timeline entries
    entries = re.split(r'\n(?=\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})', formatted)
    
    # Process each entry
    formatted_entries = []
    for entry in entries:
        if entry.strip():
            # Clean up entry
            entry = entry.strip()
            
            # Add proper spacing
            entry = re.sub(r'\s+', ' ', entry)
            
            # Add entry break
            formatted_entries.append(entry)
    
    # Join entries with line breaks
    return '\n'.join(formatted_entries)

def format_article_title(title: str) -> str:
    """Format article title for better readability"""
    if not title:
        return title
    
    # Clean up the title
    formatted = title.strip()
    
    # Remove extra spaces
    formatted = re.sub(r'\s+', ' ', formatted)
    
    # Capitalize first letter
    if formatted and not formatted[0].isupper():
        formatted = formatted[0].upper() + formatted[1:]
    
    return formatted

def format_source_name(source: str) -> str:
    """Format source name for better readability"""
    if not source:
        return source
    
    # Clean up the source
    formatted = source.strip()
    
    # Remove extra spaces
    formatted = re.sub(r'\s+', ' ', formatted)
    
    # Capitalize first letter
    if formatted and not formatted[0].isupper():
        formatted = formatted[0].upper() + formatted[1:]
    
    return formatted
