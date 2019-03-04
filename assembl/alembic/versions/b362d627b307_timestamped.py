"""timestamped

Revision ID: b362d627b307
Revises: 2eb3b92b734c
Create Date: 2019-03-03 18:30:42.103835

"""

# revision identifiers, used by Alembic.
revision = 'b362d627b307'
down_revision = '2eb3b92b734c'

from alembic import context, op
import sqlalchemy as sa
import transaction
from datetime import datetime


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.alter_column(
            'announce', 'modification_date', new_column_name='last_modified')
        # TODO: something with actions and langstrings
        op.execute('UPDATE idea SET last_modified = creation_date')

    # Do stuff with the app's models here.
    from assembl import models as m
    db = m.get_session_maker()()
    with transaction.manager:
        pass


def downgrade(pyramid_env):
    with context.begin_transaction():
        op.alter_column(
            'announce', 'last_modified', new_column_name='modification_date')
