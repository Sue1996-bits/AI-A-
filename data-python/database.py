# database.py
import json
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import create_engine, Column, Integer, String, Text, Float, DateTime, JSON
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError
import logging

from config import DATABASE_URL

logger = logging.getLogger(__name__)

Base = declarative_base()

class News(Base):
    __tablename__ = 'news'
    id = Column(Integer, primary_key=True)
    title = Column(String(512), nullable=False)
    url = Column(String(1024), unique=True, nullable=False, index=True)
    content = Column(Text, nullable=False)
    publish_time = Column(DateTime, nullable=False)
    source = Column(String(100))
    status = Column(String(50), default='pending', index=True)
    error_message = Column(Text)
    crawl_time = Column(DateTime, default=datetime.now)

class AnalysisResult(Base):
    __tablename__ = 'analysis_results'
    id = Column(Integer, primary_key=True)
    news_id = Column(Integer, nullable=False, index=True)
    summary = Column(Text)
    event_type = Column(String(255))
    core_entities = Column(JSON)
    sentiment_score = Column(Float)
    confidence = Column(Float)
    api_used = Column(String(50))
    analysis_time = Column(DateTime, default=datetime.now)
    processing_duration = Column(Float)

class NewsDatabase:
    def __init__(self):
        try:
            # 注意：SQLAlchemy的create_engine本身是同步的，但aiomysql驱动使其能被异步框架使用
            engine = create_engine(DATABASE_URL.replace("aiomysql", "pymysql")) # 使用同步版本创建表
            Base.metadata.create_all(engine)
            self.Session = sessionmaker(bind=engine)
            logger.info("数据库表结构已确认/创建。")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}", exc_info=True)
            raise

    def _execute(self, func):
        with self.Session() as session:
            try:
                result = func(session)
                session.commit()
                return result
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"数据库操作失败: {e}", exc_info=True)
                raise

    def get_news_by_url(self, url: str) -> Optional[Dict]:
        def _get(session):
            news = session.query(News).filter_by(url=url).first()
            return news.id if news else None
        return self._execute(_get)

    def save_news(self, news_data: Dict) -> int:
        def _save(session):
            new_news = News(
                title=news_data['title'],
                url=news_data['url'],
                content=news_data['content'],
                publish_time=datetime.fromisoformat(news_data['publish_time']),
                source=news_data['source'],
                crawl_time=datetime.fromisoformat(news_data['crawl_time'])
            )
            session.add(new_news)
            session.flush() # 刷新以获取ID
            return new_news.id
        return self._execute(_save)

    def save_analysis_result(self, analysis_data: Dict) -> int:
        def _save(session):
            new_analysis = AnalysisResult(**analysis_data)
            session.add(new_analysis)
            session.flush()
            return new_analysis.id
        return self._execute(_save)

    def update_news_status(self, news_id: int, status: str, error_message: str = None):
        def _update(session):
            session.query(News).filter_by(id=news_id).update({
                "status": status,
                "error_message": error_message
            })
        self._execute(_update)