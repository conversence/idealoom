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
        op.create_table('jive_source',
            sa.Column('id', sa.Integer, sa.ForeignKey(
                      'post_source.id', onupdate='CASCADE',
                      ondelete='CASCADE'), primary_key=True),
            sa.Column('group_id', sa.String(256), nullable=False),
            sa.Column('place_id', sa.String(256)),
            sa.Column('json_data', sa.Text),
            sa.Column('settings', sa.Text),
            sa.Column('addon_uuid', sa.String(80)),
            sa.Column('user_id', sa.Integer, sa.ForeignKey(
                      'agent_profile.id', onupdate='CASCADE',
                      ondelete='CASCADE')),
            sa.Column('token_type', sa.String(60)),
            sa.Column('access_token', sa.String(256)),
            sa.Column('refresh_token', sa.String(256)),
            sa.Column('expires', sa.DateTime),
            sa.Column('scope', sa.String(60)),
            sa.Column('instance_url', sa.String(256), nullable=False),
            sa.Column('csfr_state', sa.String(256))
        )

    # Do stuff with the app's models here.
    from assembl import models as m
    db = m.get_session_maker()()
    with transaction.manager:
        pass


def downgrade(pyramid_env):
    with context.begin_transaction():
        # op.drop_table('jive_addon_settings')
        op.drop_table('jive_source')
