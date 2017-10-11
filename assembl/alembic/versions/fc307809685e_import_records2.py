"""import_records2

Revision ID: fc307809685e
Revises: cde4738d5863
Create Date: 2017-10-06 11:54:07.215085

"""

# revision identifiers, used by Alembic.
revision = 'fc307809685e'
down_revision = 'cde4738d5863'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        # TODO: check if table exists
        # op.drop_table('import_record')
        op.create_table(
            'idea_source',
            sa.Column('id', sa.Integer, sa.ForeignKey('content_source.id'), primary_key=True),
            sa.Column('uri_id', sa.Integer, sa.ForeignKey('uriref.id'), nullable=False, unique=True))

    # Do stuff with the app's models here.
    from assembl import models as m
    from assembl.lib.generic_pointer import universalTableRefColType
    db = m.get_session_maker()()
    with transaction.manager:
        universalTableRefColType.create(db.bind, True)
    with context.begin_transaction():
        op.create_table(
            'import_record',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('external_id', sa.Unicode, nullable=False),
            sa.Column('source_id', sa.Integer, sa.ForeignKey(
                'idea_source.id', ondelete="CASCADE", onupdate="CASCADE"), nullable=False),
            sa.Column('last_import_time', sa.DateTime, server_default="now()"),
            sa.Column('target_id', sa.Integer, nullable=False),
            sa.Column('target_table', universalTableRefColType, nullable=False),
        )


def downgrade(pyramid_env):
    with context.begin_transaction():
        op.drop_table('import_record')
        op.drop_table('idea_source')
    from assembl import models as m
    from assembl.lib.generic_pointer import universalTableRefColType
    db = m.get_session_maker()()
    with transaction.manager:
        universalTableRefColType.drop(db.bind, True)
