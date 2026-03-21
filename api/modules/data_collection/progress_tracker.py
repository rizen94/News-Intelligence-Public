"""
Progress Tracker for RSS Collection
Tracks real-time progress of RSS feed collection operations
"""

import logging
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CollectionProgress:
    """Progress tracking for RSS collection"""

    collection_id: str
    start_time: datetime
    status: str  # 'running', 'completed', 'failed', 'cancelled'
    total_feeds: int
    processed_feeds: int
    successful_feeds: int
    failed_feeds: int
    total_articles: int
    new_articles: int
    duplicate_articles: int
    current_feed: str | None = None
    current_feed_progress: int = 0
    current_feed_total: int = 0
    errors: list = None
    end_time: datetime | None = None
    duration_seconds: float | None = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        if data["start_time"]:
            data["start_time"] = data["start_time"].isoformat()
        if data["end_time"]:
            data["end_time"] = data["end_time"].isoformat()
        return data


class ProgressTracker:
    """Thread-safe progress tracker for RSS collection operations"""

    def __init__(self):
        self._progress: dict[str, CollectionProgress] = {}
        self._lock = threading.Lock()
        self._cleanup_interval = 300  # 5 minutes
        self._max_progress_age = 3600  # 1 hour

        # Start cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_old_progress, daemon=True)
        self._cleanup_thread.start()

    def start_collection(self, collection_id: str, total_feeds: int) -> CollectionProgress:
        """
        Start tracking a new collection operation

        Args:
            collection_id: Unique identifier for this collection
            total_feeds: Total number of feeds to process

        Returns:
            CollectionProgress object
        """
        with self._lock:
            progress = CollectionProgress(
                collection_id=collection_id,
                start_time=datetime.now(),
                status="running",
                total_feeds=total_feeds,
                processed_feeds=0,
                successful_feeds=0,
                failed_feeds=0,
                total_articles=0,
                new_articles=0,
                duplicate_articles=0,
            )

            self._progress[collection_id] = progress
            logger.info(f"Started tracking collection {collection_id} with {total_feeds} feeds")

        return progress

    def update_feed_progress(
        self, collection_id: str, feed_name: str, feed_progress: int, feed_total: int
    ):
        """
        Update progress for current feed being processed

        Args:
            collection_id: Collection identifier
            feed_name: Name of current feed
            feed_progress: Articles processed in current feed
            feed_total: Total articles in current feed
        """
        with self._lock:
            if collection_id in self._progress:
                progress = self._progress[collection_id]
                progress.current_feed = feed_name
                progress.current_feed_progress = feed_progress
                progress.current_feed_total = feed_total

                logger.debug(
                    f"Collection {collection_id}: {feed_name} - {feed_progress}/{feed_total} articles"
                )

    def complete_feed(
        self,
        collection_id: str,
        feed_name: str,
        articles_collected: int,
        new_articles: int,
        duplicate_articles: int,
        success: bool = True,
    ):
        """
        Mark a feed as completed

        Args:
            collection_id: Collection identifier
            feed_name: Name of completed feed
            articles_collected: Total articles collected from feed
            new_articles: New articles added to database
            duplicate_articles: Duplicate articles found
            success: Whether feed collection was successful
        """
        with self._lock:
            if collection_id in self._progress:
                progress = self._progress[collection_id]
                progress.processed_feeds += 1
                progress.total_articles += articles_collected
                progress.new_articles += new_articles
                progress.duplicate_articles += duplicate_articles

                if success:
                    progress.successful_feeds += 1
                else:
                    progress.failed_feeds += 1

                # Clear current feed info
                progress.current_feed = None
                progress.current_feed_progress = 0
                progress.current_feed_total = 0

                logger.info(
                    f"Collection {collection_id}: Completed {feed_name} - "
                    f"{new_articles} new articles, {duplicate_articles} duplicates"
                )

    def add_error(self, collection_id: str, error_message: str):
        """
        Add an error to the collection progress

        Args:
            collection_id: Collection identifier
            error_message: Error message to add
        """
        with self._lock:
            if collection_id in self._progress:
                self._progress[collection_id].errors.append(
                    {"timestamp": datetime.now().isoformat(), "message": error_message}
                )
                logger.error(f"Collection {collection_id} error: {error_message}")

    def complete_collection(self, collection_id: str, success: bool = True):
        """
        Mark collection as completed

        Args:
            collection_id: Collection identifier
            success: Whether collection was successful
        """
        with self._lock:
            if collection_id in self._progress:
                progress = self._progress[collection_id]
                progress.status = "completed" if success else "failed"
                progress.end_time = datetime.now()
                progress.duration_seconds = (
                    progress.end_time - progress.start_time
                ).total_seconds()

                logger.info(
                    f"Collection {collection_id} completed: "
                    f"{progress.successful_feeds}/{progress.total_feeds} feeds successful, "
                    f"{progress.new_articles} new articles in {progress.duration_seconds:.1f}s"
                )

    def cancel_collection(self, collection_id: str):
        """
        Cancel a running collection

        Args:
            collection_id: Collection identifier
        """
        with self._lock:
            if collection_id in self._progress:
                progress = self._progress[collection_id]
                progress.status = "cancelled"
                progress.end_time = datetime.now()
                progress.duration_seconds = (
                    progress.end_time - progress.start_time
                ).total_seconds()

                logger.info(f"Collection {collection_id} cancelled")

    def get_progress(self, collection_id: str) -> CollectionProgress | None:
        """
        Get progress for a specific collection

        Args:
            collection_id: Collection identifier

        Returns:
            CollectionProgress object or None if not found
        """
        with self._lock:
            return self._progress.get(collection_id)

    def get_all_progress(self) -> dict[str, CollectionProgress]:
        """
        Get all active progress tracking

        Returns:
            Dictionary of collection_id -> CollectionProgress
        """
        with self._lock:
            return self._progress.copy()

    def get_active_collections(self) -> dict[str, CollectionProgress]:
        """
        Get all currently running collections

        Returns:
            Dictionary of running collections
        """
        with self._lock:
            return {
                collection_id: progress
                for collection_id, progress in self._progress.items()
                if progress.status == "running"
            }

    def _cleanup_old_progress(self):
        """Clean up old progress entries"""
        while True:
            try:
                time.sleep(self._cleanup_interval)

                with self._lock:
                    current_time = datetime.now()
                    to_remove = []

                    for collection_id, progress in self._progress.items():
                        age_seconds = (current_time - progress.start_time).total_seconds()
                        if age_seconds > self._max_progress_age:
                            to_remove.append(collection_id)

                    for collection_id in to_remove:
                        del self._progress[collection_id]
                        logger.debug(f"Cleaned up old progress for collection {collection_id}")

            except Exception as e:
                logger.error(f"Error in progress cleanup: {e}")


# Global progress tracker instance
progress_tracker = ProgressTracker()
