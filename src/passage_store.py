"""Database operations for passages, sessions, and indexing status."""
import uuid
import json
from datetime import datetime, timedelta, date, timezone
from pathlib import Path
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import List, Optional

Base = declarative_base()


class Passage(Base):
    """Passage model."""
    __tablename__ = 'passages'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    text = Column(Text, nullable=False)
    source_file = Column(String, nullable=False, index=True)  # Absolute path
    file_type = Column(String, nullable=False)  # 'txt', 'html', 'md', 'pdf'
    page_number = Column(Integer, nullable=True)  # For PDFs
    line_number = Column(Integer, nullable=True)  # For text files
    chapter = Column(String, nullable=True)
    section = Column(String, nullable=True)
    document_title = Column(String, nullable=True)
    author = Column(String, nullable=True)
    start_char = Column(Integer, nullable=False)
    end_char = Column(Integer, nullable=False)
    extracted_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    # JSON-encoded embedding vector (added in Stage 2)
    embedding = Column(Text, nullable=True)


class SessionHistory(Base):
    """Session history model - tracks passages shown per day."""
    __tablename__ = 'session_history'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_date = Column(String, nullable=False, index=True)  # YYYY-MM-DD format
    passage_id = Column(String, ForeignKey('passages.id'), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_session_date_passage', 'session_date', 'passage_id'),
    )


class IndexingStatus(Base):
    """Indexing status model - tracks file indexing state."""
    __tablename__ = 'indexing_status'
    
    file_path = Column(String, primary_key=True)  # Absolute path
    status = Column(String, nullable=False, default='pending')  # 'pending', 'indexing', 'completed', 'failed'
    indexed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class SavedPassage(Base):
    """Saved passage model - tracks user-saved passages."""
    __tablename__ = 'saved_passages'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    passage_id = Column(String, ForeignKey('passages.id'), nullable=False)
    saved_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    notes = Column(Text, nullable=True)


class UsageEvent(Base):
    """Usage events for analytics (user actions, app lifecycle, etc.)."""
    __tablename__ = 'usage_events'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    action = Column(String, nullable=False, index=True)
    passage_id = Column(String, ForeignKey('passages.id'), nullable=True, index=True)
    info = Column(Text, nullable=True)  # Optional JSON string with extra context
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class PassageStore:
    """Database operations for passages."""
    
    def __init__(self, db_path: str = 'data/passages.db'):
        """Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file.
        """
        db_path = Path(db_path)
        # Resolve relative to project root if not absolute
        if not db_path.is_absolute():
            project_root = Path(__file__).parent.parent
            db_path = project_root / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.engine = create_engine(f'sqlite:///{db_path.resolve()}', echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
    
    def get_session(self) -> Session:
        """Get a database session."""
        return self.Session()
    
    def add_passage(self, passage_data: dict) -> Passage:
        """Add a passage to the database.
        
        Args:
            passage_data: Dictionary with passage fields.
            
        Returns:
            Created Passage object.
        """
        session = self.get_session()
        try:
            passage = Passage(**passage_data)
            session.add(passage)
            session.commit()
            session.refresh(passage)
            return passage
        finally:
            session.close()
    
    def get_random_passage(self, exclude_days: int = 30) -> Optional[Passage]:
        """Get a random passage not shown in the last N days.
        
        Args:
            exclude_days: Number of days to exclude from selection.
            
        Returns:
            Random Passage or None if no passages available.
        """
        session = self.get_session()
        try:
            # Calculate cutoff date
            cutoff_date = date.today() - timedelta(days=exclude_days)
            cutoff_str = cutoff_date.strftime('%Y-%m-%d')
            
            # Get passage IDs shown in exclusion window
            shown_ids = {
                row[0] for row in session.query(SessionHistory.passage_id)
                .filter(SessionHistory.session_date >= cutoff_str)
                .all()
            }
            
            # Get a random passage not in exclusion list
            from sqlalchemy import func
            query = session.query(Passage)
            if shown_ids:
                query = query.filter(~Passage.id.in_(shown_ids))
            
            passage = query.order_by(func.random()).first()
            return passage
        finally:
            session.close()
    
    def record_session_passage(self, passage_id: str):
        """Record that a passage was shown in today's session.
        
        Args:
            passage_id: ID of the passage shown.
        """
        session = self.get_session()
        try:
            today = date.today().strftime('%Y-%m-%d')
            session_history = SessionHistory(
                session_date=today,
                passage_id=passage_id
            )
            session.add(session_history)
            session.commit()
        finally:
            session.close()
    
    def get_indexing_status(self, file_path: str) -> Optional[IndexingStatus]:
        """Get indexing status for a file.
        
        Args:
            file_path: Absolute path to file.
            
        Returns:
            IndexingStatus or None if not found.
        """
        session = self.get_session()
        try:
            return session.query(IndexingStatus).filter_by(file_path=file_path).first()
        finally:
            session.close()
    
    def set_indexing_status(self, file_path: str, status: str, error_message: Optional[str] = None):
        """Set indexing status for a file.
        
        Args:
            file_path: Absolute path to file.
            status: Status ('pending', 'indexing', 'completed', 'failed')
            error_message: Error message if status is 'failed'.
        """
        session = self.get_session()
        try:
            indexing_status = session.query(IndexingStatus).filter_by(file_path=file_path).first()
            if not indexing_status:
                indexing_status = IndexingStatus(file_path=file_path)
                session.add(indexing_status)
            
            indexing_status.status = status
            if status == 'completed':
                indexing_status.indexed_at = datetime.now(timezone.utc)
            if error_message:
                indexing_status.error_message = error_message
            
            session.commit()
        finally:
            session.close()
    
    def get_pending_files(self, limit: Optional[int] = None) -> List[str]:
        """Get list of files pending indexing.
        
        Args:
            limit: Maximum number of files to return.
            
        Returns:
            List of absolute file paths.
        """
        session = self.get_session()
        try:
            query = session.query(IndexingStatus.file_path).filter_by(status='pending')
            if limit:
                query = query.limit(limit)
            return [row[0] for row in query.all()]
        finally:
            session.close()

    def get_indexed_file_count(self) -> int:
        """Return number of files with completed indexing."""
        session = self.get_session()
        try:
            return session.query(IndexingStatus).filter_by(status="completed").count()
        finally:
            session.close()
    
    def save_passage(self, passage_id: str) -> SavedPassage:
        """Save a passage to user's collection.
        
        Args:
            passage_id: ID of passage to save.
            
        Returns:
            Created SavedPassage object.
        """
        session = self.get_session()
        try:
            saved = SavedPassage(passage_id=passage_id)
            session.add(saved)
            session.commit()
            session.refresh(saved)
            return saved
        finally:
            session.close()

    def set_passage_embedding(self, passage_id: str, embedding: List[float]) -> None:
        """Set embedding vector for a passage.
        
        Args:
            passage_id: Passage ID.
            embedding: Embedding vector as list of floats.
        """
        session = self.get_session()
        try:
            passage = session.query(Passage).filter_by(id=passage_id).first()
            if passage:
                passage.embedding = json.dumps(embedding)
                session.commit()
        finally:
            session.close()

    # -------- Usage analytics --------

    def log_usage_event(self, action: str, passage_id: Optional[str] = None, info: Optional[dict] = None) -> None:
        """Record a usage event for analytics.
        
        Args:
            action: Short action code (e.g. 'app_start', 'new', 'horizontal', 'context', 'save', 'index_batch').
            passage_id: Optional passage id associated with the event.
            info: Optional dict with extra metadata (will be JSON-encoded).
        """
        payload = None
        if info is not None:
            try:
                payload = json.dumps(info)
            except Exception:
                payload = None

        session = self.get_session()
        try:
            event = UsageEvent(
                action=action,
                passage_id=passage_id,
                info=payload,
            )
            session.add(event)
            session.commit()
        finally:
            session.close()
