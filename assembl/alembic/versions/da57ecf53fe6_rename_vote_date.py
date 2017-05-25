"""rename vote_date

Revision ID: da57ecf53fe6
Revises: 2b8cadc0af7e
Create Date: 2017-05-25 12:26:34.919489

"""

# revision identifiers, used by Alembic.
revision = 'da57ecf53fe6'
down_revision = '2b8cadc0af7e'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.alter_column(
            'idea_vote', 'vote_date', new_column_name='creation_date')


def downgrade(pyramid_env):
    with context.begin_transaction():
        op.alter_column(
            'idea_vote', 'creation_date', new_column_name='vote_date')
