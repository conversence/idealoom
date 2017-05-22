"""Users with verified social accounts should be verified

Revision ID: 2b8cadc0af7e
Revises: 7d138bea3a0d
Create Date: 2017-05-22 11:54:20.479856

"""

# revision identifiers, used by Alembic.
revision = '2b8cadc0af7e'
down_revision = '7d138bea3a0d'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    # Do stuff with the app's models here.
    from assembl import models as m
    db = m.get_session_maker()()
    with transaction.manager:
        db.query(m.User).filter(m.User.id.in_(
            db.query(m.User.id).join(m.SocialAuthAccount).filter(
                m.SocialAuthAccount.verified == True, m.User.verified == False
            ).subquery())
        ).update({"verified": True}, False)


def downgrade(pyramid_env):
    pass
