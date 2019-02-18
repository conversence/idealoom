"""publication_states

Revision ID: 10eaccaf8c33
Revises: 407441ce1b20
Create Date: 2019-02-18 10:15:15.037098

"""

# revision identifiers, used by Alembic.
revision = '10eaccaf8c33'
down_revision = '407441ce1b20'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.create_table(
            "publication_flow",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("label", sa.String(60), nullable=False, unique=True),
            sa.Column("name_id", sa.Integer(), sa.ForeignKey(
                "langstring.id", ondelete="SET NULL", onupdate="CASCADE")),
        )
        op.create_table(
            "publication_state",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("flow_id", sa.Integer, sa.ForeignKey(
                "publication_flow.id", ondelete="CASCADE", onupdate="CASCADE"),
                nullable=False, index=True),
            sa.Column("label", sa.String(60), nullable=False),
            sa.Column("name_id", sa.Integer(), sa.ForeignKey(
                "langstring.id", ondelete="SET NULL", onupdate="CASCADE")),
            sa.UniqueConstraint('flow_id', 'label'),
        )
        op.create_table(
            "publication_transition",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("flow_id", sa.Integer, sa.ForeignKey(
                "publication_flow.id", ondelete="CASCADE", onupdate="CASCADE"),
                nullable=False, index=True),
            sa.Column("source_id", sa.Integer, sa.ForeignKey(
                "publication_state.id", ondelete="CASCADE", onupdate="CASCADE"),
                nullable=False, index=True),
            sa.Column("target_id", sa.Integer, sa.ForeignKey(
                "publication_state.id", ondelete="CASCADE", onupdate="CASCADE"),
                nullable=False, index=True),
            sa.Column("label", sa.String(60), nullable=False),
            sa.Column("name_id", sa.Integer(), sa.ForeignKey(
                "langstring.id", ondelete="SET NULL", onupdate="CASCADE")),
            sa.UniqueConstraint('flow_id', 'label'),
        )

    # Do stuff with the app's models here.
    from assembl import models as m
    db = m.get_session_maker()()
    with transaction.manager:
        pass


def downgrade(pyramid_env):
    with context.begin_transaction():
        op.drop_table("publication_transition")
        op.drop_table("publication_state")
        op.drop_table("publication_flow")
