#!/usr/bin/env python3
"""
Targeted fix for specific problematic lines
"""

def fix_news_aggregation():
    file_path = "domains/news_aggregation/routes/news_aggregation.py"
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Fix specific problematic lines
    for i, line in enumerate(lines):
        if "summary, quality_score, word_count" in line:
            print(f"Found problematic line {i+1}: {line.strip()}")
            lines[i] = line.replace("summary, quality_score, word_count,", "content,")
            print(f"Fixed line {i+1}: {lines[i].strip()}")
        
        if "quality_score" in line and "row[" in line:
            print(f"Found quality_score reference line {i+1}: {line.strip()}")
            lines[i] = line.replace('"quality_score": row[6],', '"content": row[2],')
            print(f"Fixed line {i+1}: {lines[i].strip()}")
        
        if "SELECT AVG(quality_score)" in line:
            print(f"Found quality_score query line {i+1}: {line.strip()}")
            lines[i] = line.replace("SELECT AVG(quality_score)", "SELECT AVG(LENGTH(content))")
            print(f"Fixed line {i+1}: {lines[i].strip()}")
    
    with open(file_path, 'w') as f:
        f.writelines(lines)
    
    print("✅ News aggregation routes fixed")

fix_news_aggregation()
