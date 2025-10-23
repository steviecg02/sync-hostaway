from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.

    All models in this application inherit from this base class to provide
    consistent table metadata and ORM functionality across the database schema.
    """

    pass
