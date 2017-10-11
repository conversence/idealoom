"""imported_voter

Revision ID: cde4738d5863
Revises: aad68410c38b
Create Date: 2017-10-11 13:05:32.520880

"""

# revision identifiers, used by Alembic.
revision = 'cde4738d5863'
down_revision = 'aad68410c38b'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.drop_constraint('idea_vote_voter_id_fkey', 'idea_vote')
        op.create_foreign_key(
            "idea_vote_voter_id_fkey", "idea_vote",
            "agent_profile", ["voter_id"], ["id"])

def downgrade(pyramid_env):
    with context.begin_transaction():
        op.drop_constraint('idea_vote_voter_id_fkey', 'idea_vote')
        op.create_foreign_key(
            "idea_vote_voter_id_fkey", "idea_vote",
            "user", ["voter_id"], ["id"])
