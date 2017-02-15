"""kill username table

Revision ID: e68cb9383f0c
Revises: 164b0fe5831b
Create Date: 2017-02-15 10:51:32.662465

"""

# revision identifiers, used by Alembic.
revision = 'e68cb9383f0c'
down_revision = '164b0fe5831b'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.add_column(
            'user', sa.Column('username', sa.Unicode(20), unique=True))
        op.execute("""UPDATE public.user SET username = (
            SELECT username FROM username
            WHERE username.user_id = public.user.id)""")
        op.drop_table('username')


def downgrade(pyramid_env):
    with context.begin_transaction():
        op.create_table(
            'username',
            sa.Column('user_id', sa.Integer, sa.ForeignKey(
                      'user.id', ondelete='CASCADE', onupdate='CASCADE'),
                      nullable=False, unique=True, index=True),
            sa.Column('username', sa.Unicode(20), primary_key=True))
        op.execute("""INSERT INTO username (user_id, username)
            SELECT id, username FROM public.user
            WHERE username IS NOT NULL""")
        op.drop_column('user', 'username')
