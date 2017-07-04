"""idea_link creation

Revision ID: 30365b67b36d
Revises: da57ecf53fe6
Create Date: 2017-05-26 16:58:12.445553

"""

# revision identifiers, used by Alembic.
from builtins import str
revision = '30365b67b36d'
down_revision = 'da57ecf53fe6'

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.sql.functions import count
from sqlalchemy.sql import distinct
import transaction


from assembl.lib import config
from assembl.lib.sqla import mark_changed


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.add_column(
            "idea_idea_link", sa.Column("creation_date", sa.DateTime))

    # Do stuff with the app's models here.
    from assembl import models as m
    db = m.get_session_maker()()
    with transaction.manager:
        # most cases: take the original target.
        db.execute("""UPDATE idea_idea_link AS il1
            SET creation_date = (
                SELECT DISTINCT ON (il2.base_id) i.creation_date FROM idea AS i
                JOIN idea_idea_link AS il2 ON (i.id = il2.target_id)
                WHERE il2.base_id = il1.base_id
                ORDER BY il2.base_id, il2.tombstone_date NULLS LAST)""")
        # Some links with the same target_id were not unified.
        # ALSO: Some links are pointing to the target tombstone?
        r = list(db.execute("""SELECT target_id, array_agg(base_id)
                FROM idea_idea_link
                GROUP BY target_id
                HAVING count(DISTINCT base_id) > 1"""))
        for target, bases in r:
            assert db.query(count(distinct(m.IdeaLink.target_id))).filter(
                m.IdeaLink.base_id.in_(bases)).first() == (1,)
            assert db.query(count(m.IdeaLink.id)).filter(
                m.IdeaLink.base_id.in_(bases),
                m.IdeaLink.tombstone_date == None).first()[0] <= 1
            bases.sort()
            first = bases[0]
            db.execute("""UPDATE idea_idea_link
                SET base_id = %d,
                creation_date = (SELECT creation_date FROM idea_idea_link AS il2 WHERE base_id=%d LIMIT 1)
                WHERE base_id IN (%s)
                """ % (first, first, ','.join([str(id) for id in bases[1:]])))
        mark_changed()


def downgrade(pyramid_env):
    with context.begin_transaction():
        op.drop_column("idea_idea_link", "creation_date")
