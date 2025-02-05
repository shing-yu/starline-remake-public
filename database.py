from sqlalchemy import Column, String, Text, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config import config

Base = declarative_base()


class Books(Base):
    __tablename__ = "books"
    book_id: Column = Column(String(180), primary_key=True)
    content: Column = Column(Text)


class Chapters(Base):
    __tablename__ = "chapters"
    item_id: Column = Column(String(180), primary_key=True)
    content: Column = Column(Text)
    book_id: Column = Column(String(180))


engine = create_engine(config.sqlite.url, echo=False, isolation_level="READ UNCOMMITTED")
Base.metadata.create_all(engine)


def get_session():
    session = sessionmaker(bind=engine)
    return session()
