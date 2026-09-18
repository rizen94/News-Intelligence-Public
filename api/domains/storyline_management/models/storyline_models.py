from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import List, Optional

Base = declarative_base()

class Storyline(Base):
    __tablename__ = "storylines"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), index=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    metadata_json = Column(JSON)
    
    # Relationship to storyline articles
    storyline_articles = relationship("StorylineArticle", back_populates="storyline")

class StorylineArticle(Base):
    __tablename__ = "storyline_articles"
    
    id = Column(Integer, primary_key=True, index=True)
    storyline_id = Column(Integer, ForeignKey("storylines.id"))
    article_id = Column(String(255), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_processed = Column(Boolean, default=False)
    
    # Relationship to storyline
    storyline = relationship("Storyline", back_populates="storyline_articles")