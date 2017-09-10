from sqlalchemy import (Column, Integer)

from ..lib.sqla_types import URIRefString
from . import Base


class URIRefDb(Base):
    __tablename__ = "uriref"
    id = Column(Integer, primary_key=True)
    # Maybe an indicator to distinguish types, properties, blanks, seqs...
    val = Column(URIRefString, nullable=False, unique=True)
