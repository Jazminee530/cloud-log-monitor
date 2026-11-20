from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db():
    # Import model definitions so SQLAlchemy knows which tables to create.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db():
    with SessionLocal() as session:
        yield session
