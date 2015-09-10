"""jive

Revision ID: 19c3d31aaa8b
Revises: 1e1d2b26db86
Create Date: 2015-09-09 15:32:55.774377

"""

# revision identifiers, used by Alembic.
revision = '19c3d31aaa8b'
down_revision = '1e1d2b26db86'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.create_table('jive_group_source',
            sa.Column('id', sa.Integer, sa.ForeignKey(
                      'post_source.id', onupdate='CASCADE',
                      ondelete='CASCADE'), primary_key=True),
            sa.Column('group_id', sa.String(256), nullable=False),
            sa.Column('place_id', sa.String(256)),
            sa.Column('json_data', sa.Text),
            sa.Column('settings', sa.Text),
            sa.Column('addon_uuid', sa.String(80))
        )

        # op.create_table('jive_addon_settings',
        #     sa.Column('id', sa.Integer, primary_key=True),
        #     sa.Column('source_id', sa.Integer, sa.ForeignKey(
        #               'jive_group_source.id', onupdate='CASCADE',
        #               ondelete='CASCADE'), nullable=False),
        #     sa.Column('json_data', sa.Text, nullable=False),
        # )

    # Do stuff with the app's models here.
    from assembl import models as m
    db = m.get_session_maker()()
    with transaction.manager:
        pass


def downgrade(pyramid_env):
    with context.begin_transaction():
        # op.drop_table('jive_addon_settings')
        op.drop_table('jive_group_source')
