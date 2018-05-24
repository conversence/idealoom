"""DiscussionAgent

Revision ID: 98c1d668f1fc
Revises: 407441ce1b20
Create Date: 2018-05-17 17:41:46.045203

"""

# revision identifiers, used by Alembic.
revision = '98c1d668f1fc'
down_revision = '407441ce1b20'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config
from assembl.lib.sqla import mark_changed

changes = [
    ['discussion', [()], 'creator_dagent_id', 'creator_id', True, False],
    ['local_user_role', [()], 'dagent_id', 'user_id', False, True],
    ['discussion_peruser_namespaced_key_value', [()], 'dagent_id', 'user_id', False, False],
        # public_assembl_discussion_peruser_namespaced_key_value_unique_c
    ['extract', [()], 'attributed_to_dagent_id', 'attributed_to_id', True, False],
    ['extract', [()], 'owner_dagent_id', 'owner_id', True, False],
    ['idea_vote', [[('idea', 'idea_id')]], 'voter_dagent_id', 'voter_id', True, True],
        # ix_public_idea_vote_voter_id
    ['attachment', [()], 'creator_dagent_id', 'creator_id', True, False],
    ['announce', [()], 'creator_dagent_id', 'creator_id', True, False],
    ['announce', [()], 'last_updated_by_dagent_id', 'last_updated_by_id', True, False],
    ['widget_user_config', [[('widget', 'widget_id')]], 'dagent_id', 'user_id', False, True],
        # ix_public_widget_user_config_user_id
    ['post', [[('content', 'id')]], 'creator_dagent_id', 'creator_id', True, True],
        # ix_public_post_creator_id
    ['notification_subscription', [()], 'dagent_id', 'user_id', False, True],
    ['notification_subscription_on_useraccount', [[('notification_subscription', 'id')]], 'on_dagent_id', 'on_user_id', False, False],
    ['idea_content_link', [[('content', 'content_id')]], 'creator_dagent_id', 'creator_id', True, False],
    ['action', [[('action_on_post', 'id'), ('content', 'post_id')],
                [('action_on_idea', 'id'), ('idea', 'idea_id')]],
                'actor_dagent_id', 'actor_id', False, True],
    # ix_public_action_actor_id
]

def upgrade(pyramid_env):
    with context.begin_transaction():
        # if False:
        op.add_column(
            'agent_status_in_discussion',
            sa.Column('template', sa.Boolean, server_default='false'))
        op.add_column(
            'agent_status_in_discussion',
            sa.Column('forget_identity', sa.Boolean, server_default='false'))
        op.add_column(
            'agent_status_in_discussion',
            sa.Column('always_pseudonymize', sa.Boolean, server_default='false'))
        op.add_column(
            'agent_status_in_discussion',
            sa.Column('pseudonym', sa.Unicode(40)))
        op.create_unique_constraint(
            'agent_status_in_discussion_discussion_id_pseudonym_key',
            'agent_status_in_discussion', ['discussion_id', 'pseudonym'])
        for table, joins, colname, oldcol, nullable, index in changes:
            op.add_column(
                table, sa.Column(
                    colname, sa.Integer,
                    sa.ForeignKey('agent_status_in_discussion.id',
                                  ondelete='SET NULL' if nullable else 'CASCADE',
                                  onupdate='CASCADE')))
            if index:
                index_name = "ix_public_{table}_{oldcol}".format(table=table, oldcol=oldcol)
                op.drop_index(index_name, table)
            if not nullable:
                op.alter_column(table, oldcol, nullable=True)
            if table == 'discussion_peruser_namespaced_key_value':
                op.drop_constraint(
                    'public_assembl_discussion_peruser_namespaced_key_value_unique_c', table, 'unique')
        op.alter_column('agent_status_in_discussion', 'profile_id', nullable=True)

    # Do stuff with the app's models here.
    from assembl import models as m
    db = m.get_session_maker()()
    with transaction.manager:
        # if False:
        # TODO: Add P_SEE_IDENTITY for all roles which have P_READ, except Everyone/Authenticated
        # Then, add P_READ to anyone who has P_READ_PUBLIC_CIF, and blast P_READ_PUBLIC_CIF
        # Add missing DiscussionAgents. Some of them will have spuriously empty last_login etc.
        missing = set()
        for table, joins, colname, oldcol, nullable, index in changes:
            for join_spec in joins:
                join_clause = []
                base_table = table
                for jtable, jcol in join_spec:
                    join_clause.append("JOIN {jtable} ON {base_table}.{jcol} = {jtable}.id".format(
                        jtable=jtable, base_table=base_table, jcol=jcol))
                    base_table = jtable
                join_clause = '\n'.join(join_clause)
                discid = 'id' if table == 'discussion' else 'discussion_id'
                query = """SELECT DISTINCT {disc_table}.{discid} as discussion_id,
                        {table}.{oldcol} as user_id
                    FROM {table} {join_clause}
                    JOIN agent_profile ON agent_profile.id = {table}.{oldcol}
                    LEFT OUTER JOIN agent_status_in_discussion ON agent_status_in_discussion.profile_id = agent_profile.id
                    AND agent_status_in_discussion.discussion_id = {disc_table}.{discid}
                    WHERE agent_status_in_discussion IS NULL""".format(
                        disc_table = base_table, table=table, join_clause=join_clause, oldcol=oldcol, discid=discid)
                missing.update([(d, u) for (d, u) in db.execute(query)])
        db.execute(
            'INSERT INTO agent_status_in_discussion (discussion_id, profile_id) VALUES ' +
                ", ".join("(%d, %d)" % t for t in missing))
        mark_changed()
    with transaction.manager:
        # if False:
        # Set the dagent values
        for table, joins, colname, oldcol, nullable, index in changes:
            for join_spec in joins:
                join_clause = []
                base_table = table
                for jtable, jcol in join_spec:
                    join_clause.append("JOIN {jtable} ON {base_table}.{jcol} = {jtable}.id".format(
                        jtable=jtable, base_table=base_table, jcol=jcol))
                    base_table = jtable
                join_clause = '\n'.join(join_clause)
                discid = 'id' if table == 'discussion' else 'discussion_id'
                query = """SELECT {table}.id as id, agent_status_in_discussion.id as dagid
                    FROM {table} {join_clause}
                    JOIN agent_profile ON agent_profile.id = {table}.{oldcol}
                    JOIN agent_status_in_discussion ON agent_status_in_discussion.profile_id = agent_profile.id
                    AND agent_status_in_discussion.discussion_id = {disc_table}.{discid}""".format(
                        disc_table = base_table, table=table, join_clause=join_clause, oldcol=oldcol, discid=discid)
                update = """WITH up AS ({query})
                    UPDATE {table} SET {colname}=up.dagid FROM up
                    WHERE {table}.id=up.id""".format(table=table, query=query, colname=colname)
                db.execute(update)
        # make some agent_profiles into user templates
        db.execute("""UPDATE agent_status_in_discussion
            SET template=true
            WHERE id IN (
                SELECT agent_status_in_discussion.id
                FROM agent_status_in_discussion
                JOIN agent_profile
                    ON agent_status_in_discussion.profile_id=agent_profile.id
                WHERE agent_profile.type='user_template')""")
        db.execute("""INSERT INTO local_user_role (dagent_id, discussion_id, role_id)
            SELECT agent_status_in_discussion.id,
                agent_status_in_discussion.discussion_id,
                user_template.role_id
            FROM agent_status_in_discussion JOIN user_template
            ON agent_status_in_discussion.profile_id=user_template.id""")
        db.execute("UPDATE agent_status_in_discussion SET profile_id = NULL WHERE template=true")
        db.execute("DELETE FROM public.user WHERE id IN (SELECT id FROM user_template)")
        db.execute("DELETE FROM agent_profile WHERE id IN (SELECT id FROM user_template)")
        mark_changed()
    with context.begin_transaction():
        for table, joins, colname, oldcol, nullable, index in changes:
            if table == 'discussion_peruser_namespaced_key_value':
                op.create_unique_constraint(
                    'discussion_peruser_namespaced_key_value_unique_c',
                    table, ['discussion_id', 'namespace', 'key', 'dagent_id'])
            if not nullable:
                op.execute("DELETE FROM {table} WHERE {colname} IS NULL".format(
                    table=table, colname=colname))
                op.alter_column(table, colname, nullable=False)
            # op.drop_column(table, oldcol)
            if index:
                index_name = "ix_public_{table}_{colname}".format(table=table, colname=colname)
                op.create_index(index_name, table, [colname])
        # op.drop_table('user_template')


