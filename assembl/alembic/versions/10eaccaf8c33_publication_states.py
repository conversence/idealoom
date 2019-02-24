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
            sa.Column("label", sa.String(), nullable=False, unique=True),
            sa.Column("name_id", sa.Integer(), sa.ForeignKey(
                "langstring.id", ondelete="SET NULL", onupdate="CASCADE")),
        )
        op.create_table(
            "publication_state",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("flow_id", sa.Integer, sa.ForeignKey(
                "publication_flow.id", ondelete="CASCADE", onupdate="CASCADE"),
                nullable=False, index=True),
            sa.Column("label", sa.String(), nullable=False),
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
                nullable=True, index=True),
            sa.Column("target_id", sa.Integer, sa.ForeignKey(
                "publication_state.id", ondelete="CASCADE", onupdate="CASCADE"),
                nullable=False, index=True),
            sa.Column("requires_permission_id", sa.Integer, sa.ForeignKey(
                "permission.id", ondelete="CASCADE", onupdate="CASCADE"),
                nullable=False),
            sa.Column("label", sa.String(), nullable=False),
            sa.Column("name_id", sa.Integer(), sa.ForeignKey(
                "langstring.id", ondelete="SET NULL", onupdate="CASCADE")),
            sa.UniqueConstraint('flow_id', 'label'),
        )

        op.create_table(
            'idea_user_role',
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("profile_id", sa.Integer, sa.ForeignKey(
                'agent_profile.id', ondelete='CASCADE', onupdate='CASCADE'),
                nullable=False, index=True),
            sa.Column("role_id", sa.Integer, sa.ForeignKey(
                'role.id', ondelete='CASCADE', onupdate='CASCADE'),
                nullable=False, index=True),
            sa.Column("idea_id", sa.Integer, sa.ForeignKey(
                'idea.id', ondelete='CASCADE', onupdate='CASCADE'),
                nullable=False, index=True)
        )


        op.create_table(
            'state_discussion_permission',
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("discussion_id", sa.Integer, sa.ForeignKey(
                'discussion.id', ondelete='CASCADE', onupdate='CASCADE'),
                nullable=False, index=True),
            sa.Column("role_id", sa.Integer, sa.ForeignKey(
                'role.id', ondelete='CASCADE', onupdate='CASCADE'),
                nullable=False, index=True),
            sa.Column("permission_id", sa.Integer, sa.ForeignKey(
                'permission.id', ondelete='CASCADE', onupdate='CASCADE'),
                nullable=False, index=True),
            sa.Column("pub_state_id", sa.Integer, sa.ForeignKey(
                'publication_state.id', ondelete='CASCADE', onupdate='CASCADE'),
                nullable=False, index=True)
        )
        op.add_column(
            'idea', sa.Column("creator_id", sa.Integer, sa.ForeignKey(
                "agent_profile.id", ondelete="SET NULL", onupdate="CASCADE")))
        op.add_column(
            'idea', sa.Column("pub_state_id", sa.Integer, sa.ForeignKey(
                "publication_state.id", ondelete="SET NULL", onupdate="CASCADE")))

        op.add_column('idea_source', sa.Column('data_filter', sa.String))
        op.add_column(
            'idea_source', sa.Column('target_state_id', sa.Integer, sa.ForeignKey(
                'publication_state.id', ondelete="SET NULL", onupdate="CASCADE")))

        op.drop_constraint('local_user_role_user_id_fkey', 'local_user_role')
        op.alter_column('local_user_role', 'user_id', new_column_name='profile_id')
        op.create_foreign_key(
            'local_user_role_profile_id_fkey',
            'local_user_role', 'agent_profile',
            ['profile_id'], ['id'],
            ondelete='CASCADE', onupdate='CASCADE')
        op.drop_constraint('user_role_user_id_fkey', 'user_role')
        op.alter_column('user_role', 'user_id', new_column_name='profile_id')
        op.create_foreign_key(
            'user_role_profile_id_fkey',
            'user_role', 'agent_profile',
            ['profile_id'], ['id'],
            ondelete='CASCADE', onupdate='CASCADE')


    # Do stuff with the app's models here.
    from assembl import models as m
    db = m.get_session_maker()()
    with transaction.manager:
        pass
        # maybe set idea.creator_id to that of discussion, if any?


def downgrade(pyramid_env):
    with context.begin_transaction():
        op.drop_table('idea_user_role')
        op.drop_column('idea', "creator_id")
        op.drop_column('idea', "pub_state_id")
        op.drop_column('idea_source', 'data_filter')
        op.drop_column('idea_source', 'target_state_id')
        op.drop_table("state_discussion_permission")
        op.drop_table("publication_transition")
        op.drop_table("publication_state")
        op.drop_table("publication_flow")
        op.drop_constraint('local_user_role_profile_id_fkey', 'local_user_role')
        op.alter_column('local_user_role', 'profile_id', new_column_name='user_id')
        op.create_foreign_key(
            'local_user_role_user_id_fkey',
            'local_user_role', 'user',
            ['user_id'], ['id'],
            ondelete='CASCADE', onupdate='CASCADE')
        op.drop_constraint('user_role_profile_id_fkey', 'user_role')
        op.alter_column('user_role', 'profile_id', new_column_name='user_id')
        op.create_foreign_key(
            'user_role_user_id_fkey',
            'user_role', 'user',
            ['user_id'], ['id'],
            ondelete='CASCADE', onupdate='CASCADE')
