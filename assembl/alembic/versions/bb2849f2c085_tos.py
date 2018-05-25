"""tos

Revision ID: bb2849f2c085
Revises: cfdb3b895127
Create Date: 2018-05-24 15:48:40.458645

"""

# revision identifiers, used by Alembic.
revision = 'bb2849f2c085'
down_revision = 'cfdb3b895127'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.add_column(
            'agent_status_in_discussion',
            sa.Column('accepted_tos_version', sa.Integer))

    # Do stuff with the app's models here.
    from assembl import models as m
    db = m.get_session_maker()()
    with transaction.manager:
        pass


def downgrade(pyramid_env):
    with context.begin_transaction():
        pass
