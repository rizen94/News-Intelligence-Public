"""Executors package — modular task handlers extracted from AutomationManager."""

from .collection_executor import CollectionExecutor
from .nlp_executor import NlpPipelineExecutor
from .document_executor import DocumentExecutor

__all__ = ["CollectionExecutor", "NlpPipelineExecutor", "DocumentExecutor"]