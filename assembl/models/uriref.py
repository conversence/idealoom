from sqlalchemy import (Column, Integer)
from sqlalchemy.sql import functions

from ..lib.sqla_types import URIRefString
from . import Base
from ..semantic.namespaces import *
from ..semantic import jsonld_context


# Base values. Only ever append to this, order cannot be changed
base_urirefs = [
    IDEA.GenericIdeaNode,
    IDEA.InclusionRelation,
    ASSEMBL.RootIdea,
    OWL.Class,
    RDF.Property,
]


class URIRefDb(Base):
    __tablename__ = "uriref"
    id = Column(Integer, primary_key=True)
    # Maybe an indicator to distinguish types, properties, blanks, seqs...
    val = Column(URIRefString, nullable=False, unique=True)

    _protected_id = 1000

    base_uriref_nums = {uriref: num + 1 for (num, uriref) in enumerate(base_urirefs)}

    @property
    def as_curie(self):
        ctx = jsonld_context()
        return ctx.shrink_iri(self.val)

    @property
    def as_context(self):
        ctx = jsonld_context()
        val = str(self.val)
        t = ctx.find_term(val) or ctx.find_term(val, '@id')
        if t:
            return t.name

    @classmethod
    def get_or_create(cls, uri_ref, session=None):
        session = session or cls.default_db
        r = session.query(cls).filter_by(val=uri_ref).first()
        if not r:
            r = cls(val=uri_ref)
            session.add(r)
        return r

    @classmethod
    def get_or_create_from_curie(cls, curie, session=None):
        ctx = jsonld_context()
        return cls.get_or_create(ctx.expand(curie), session=session)

    @classmethod
    def get_or_create_from_ctx(cls, ctx_name, session=None):
        ctx = jsonld_context()
        term = ctx.terms.get(ctx_name, None)
        if term is not None:
            return cls.get_or_create(term.id, session=session)

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
            num += 1  # counting from 1
            if num in existing:
                assert uriref == existing[num]
            else:
                missing.append(cls(id=num, val=uriref))
        if missing:
            db.bulk_save_objects(missing)
        maxid = db.query(functions.max(cls.id)).one()[0] or 0
        if maxid < cls._protected_id:
            db.execute("select setval('uriref_id_seq'::regclass, %d)" % cls._protected_id)
