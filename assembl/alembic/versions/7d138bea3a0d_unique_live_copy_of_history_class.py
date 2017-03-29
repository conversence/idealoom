"""unique live copy of history class

Revision ID: 7d138bea3a0d
Revises: f6b4dabfe49e
Create Date: 2017-03-29 12:11:10.790333

"""

# revision identifiers, used by Alembic.
revision = '7d138bea3a0d'
down_revision = 'f6b4dabfe49e'

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.sql import func
import transaction


from assembl.lib import config
from assembl.lib.sqla import mark_changed


def upgrade(pyramid_env):
    # Do stuff with the app's models here.
    from assembl import models as m
    from assembl.lib.history_mixin import HistoryMixin
    db = m.get_session_maker()()
    with transaction.manager:
        # first find duplicates. Lossy.
        for cls in m.Base.get_subclasses():
            if (issubclass(cls, HistoryMixin) and
                    cls == cls.base_polymorphic_class()):
                t = cls.__table__
                base_ids_with_dups = db.query(t.c.base_id
                    ).filter(t.c.tombstone_date == None
                    ).group_by(t.c.base_id
                    ).having(func.count(t.c.id) > 1)
                for (base_id,) in base_ids_with_dups:
                    objs = db.query(cls
                        ).filter_by(base_id=base_id
                        ).order_by(cls.id).all()
                    # keep the last one
                    objs.pop()
                    for obj in objs:
                        obj.delete()
                    mark_changed()
    # then create indices.
    with context.begin_transaction():
        for cls in m.Base.get_subclasses():
            if (issubclass(cls, HistoryMixin) and
                    cls == cls.base_polymorphic_class()):
                op.execute(sa.schema.CreateIndex(cls.base_id_live_index()))


def downgrade(pyramid_env):
    from assembl import models as m
    from assembl.lib.history_mixin import HistoryMixin
    with context.begin_transaction():
        for cls in m.Base.get_subclasses():
            if (issubclass(cls, HistoryMixin) and
                    cls == cls.base_polymorphic_class()):
                tname = cls.__tablename__
                op.drop_index(tname + "_base_id_live_ix", tname)
