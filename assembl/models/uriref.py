from sqlalchemy import (Column, Integer)
from sqlalchemy.sql import functions

from ..lib.sqla_types import URIRefString
from . import Base
from ..semantic.namespaces import *


# Base values. Only ever append to this, order cannot be changed
base_urirefs = [
    IDEA.GenericIdeaNode,
    IDEA.InclusionRelation,
]


class URIRefDb(Base):
    __tablename__ = "uriref"
    id = Column(Integer, primary_key=True)
    # Maybe an indicator to distinguish types, properties, blanks, seqs...
    val = Column(URIRefString, nullable=False, unique=True)

    _protected_id = 1000

    base_uriref_nums = {uriref: num + 1 for (num, uriref) in enumerate(base_urirefs)}

    @classmethod
    def get_or_create(cls, uri_ref, session=None):
        session = session or cls.default_db
        r = session.query(cls).filter_by(val=uri_ref).first()
        if not r:
            r = cls(val=uri_ref)
            session.add(r)
        return r

    @classmethod
    def index_of(cls, uri_ref):
        index =  cls.base_uriref_nums.get(uri_ref, None)
        if index is not None:
            return index
        r = cls.default_db.query(cls.id).filter_by(val=uri_ref).first()
        if r:
            return r[0]

    @classmethod
    def populate_db(cls, db):
        db.execute("lock table %s in exclusive mode" % cls.__table__.name)
        assert len(base_urirefs) < cls._protected_id
        existing = db.query(cls).filter(cls.id < cls._protected_id).all()
        existing = {r.id: r.val for r in existing}
        missing = []
        for (num, uriref) in enumerate(base_urirefs):
            if num in existing:
                assert uriref == existing[num]
            else:
                missing.append(cls(id=num + 1, val=uriref))
        if missing:
            db.bulk_save_objects(missing)
        maxid = db.query(functions.max(cls.id)).one()[0] or 0
        if maxid < cls._protected_id:
            db.execute("select setval('uriref_id_seq'::regclass, %d)" % cls._protected_id)
