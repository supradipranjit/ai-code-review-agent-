from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from database import Base


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id = Column(Integer, primary_key=True, index=True)
    repo_name = Column(String, nullable=False)
    pr_number = Column(Integer, nullable=False)
    diff = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class ReviewResult(Base):
    __tablename__ = "review_results"

    id = Column(Integer, primary_key=True, index=True)
    pr_id = Column(Integer)
    file_name = Column(String, nullable=True)
    agent_type = Column(String)
    issue = Column(Text)
    severity = Column(String)
    fix = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
