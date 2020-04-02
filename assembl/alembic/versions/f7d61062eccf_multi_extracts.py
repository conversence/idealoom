"""multi extracts

Revision ID: f7d61062eccf
Revises: ca1c445a2e24
Create Date: 2020-03-30 14:57:26.093052

"""

# revision identifiers, used by Alembic.
revision = 'f7d61062eccf'
down_revision = 'ca1c445a2e24'

from collections import defaultdict
from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config
from assembl.lib.sqla import get_session_maker, mark_changed


def upgrade(pyramid_env):
    db = get_session_maker()()
    with transaction.manager:
        max_cl_id = db.query("max(id) from idea_content_link").one()[0]
        print(max_cl_id)

    with context.begin_transaction():
        op.drop_constraint('extract_id_fkey', 'extract')
        op.execute(
            f"CREATE SEQUENCE extract_id_seq START {max_cl_id+1}")
        op.alter_column('extract', 'id',
                        server_default=sa.text("nextval('extract_id_seq'::regclass)"))
        op.drop_table('idea_related_post_link')
        op.drop_table('idea_content_widget_link')
        op.drop_table('idea_content_positive_link')
        op.drop_table('idea_thread_context_break_link')
        op.drop_table('idea_content_negative_link')
        op.add_column(
            'idea_content_link',
            sa.Column('extract_id', sa.Integer, sa.ForeignKey(
                'extract.id', ondelete='CASCADE', onupdate='CASCADE')), index=True)
        op.add_column(
            'extract',
            sa.Column(
                'content_id', sa.Integer, sa.ForeignKey(
                    'content.id', ondelete="CASCADE", onupdate="CASCADE"),
                index=True))
        # rather than renaming owner...
        op.add_column(
            'extract',
            sa.Column(
                'creator_id', sa.Integer, sa.ForeignKey(
                    'agent_profile.id',
                    ondelete="SET NULL", onupdate="CASCADE")))
        op.add_column('extract', sa.Column('creation_date', sa.DateTime))
        op.execute(
            """UPDATE idea_content_link SET extract_id=id
            WHERE type='assembl:postExtractRelatedToIdea'""")
        op.execute(
            """UPDATE extract SET (content_id, creator_id, creation_date) = (
                SELECT content_id, creator_id, creation_date FROM idea_content_link
                WHERE idea_content_link.id = extract.id)""")
        op.drop_column('extract', 'owner_id')
        op.alter_column('extract', 'content_id', nullable=False)
        op.alter_column('extract', 'creation_date', nullable=False)
        op.execute("DELETE FROM idea_content_link WHERE idea_id IS NULL")
        op.alter_column('idea_content_link', 'idea_id', nullable=False)
        op.drop_constraint('idea_content_link_idea_id_fkey', 'idea_content_link')
        op.create_foreign_key(
            'idea_content_link_idea_id_fkey', 'idea_content_link', 'idea',
            ['idea_id'], ['id'], ondelete='CASCADE', onupdate='CASCADE')


def downgrade(pyramid_env):
    db = get_session_maker()()
    with transaction.manager:
        db.execute("ALTER TABLE idea_content_link ALTER COLUMN idea_id DROP NOT NULL")
        db.execute("""INSERT INTO idea_content_link 
                (type, "order", content_id, creator_id, creation_date, extract_id)
            SELECT 'assembl:postExtractRelatedToIdea', 0, extract.content_id,
                extract.creator_id, extract.creation_date, extract.id
            FROM extract
            LEFT OUTER JOIN idea_content_link as icl ON (icl.extract_id = extract.id)
            WHERE icl.id IS NULL
            """) 
        connected_extracts = list(db.execute(
            """SELECT id, extract_id from idea_content_link
            WHERE extract_id IS NOT NULL"""))
        # first remove an arbitrary ICL if two of them point to same extract
        by_extract = defaultdict(list)
        for (icl, e) in connected_extracts:
            by_extract[e].append(icl)
        duplicates = set()
        for e, icls in by_extract.items():
            if len(icls) > 1:
                if e in icls:
                    keep = e
                else:
                    keep = min(*icls)
                dups = set(icls)
                dups.remove(keep)
                duplicates.update(dups)
        if duplicates:
            db.execute("DELETE FROM idea_content_link WHERE id IN (%s)" % (
                ",".join([str(x) for x in duplicates])))
            connected_extracts = [(icl, e) for (icl, e) in connected_extracts
                                  if icl not in duplicates]
        mismatched = [(icl, e) for (icl, e) in connected_extracts if icl != e]
        if mismatched:
            # We actually need to renumber both...
            (max_extract, max_icl) = list(db.execute(
                """SELECT nextval('extract_id_seq'::regclass),
                    nextval('idea_content_link_id_seq'::regclass)"""))[0]
            if max_extract > max_icl:
                list(db.execute(
                    f"SELECT setval('idea_content_link_id_seq'::regclass, {max_extract})"))
            for icl, e in mismatched:
                val = list(db.execute(
                    "SELECT nextval('idea_content_link_id_seq'::regclass)"))[0][0]
                db.execute(
                    f"UPDATE idea_content_link SET id={val} WHERE id = {icl}")
                db.execute(
                    f"UPDATE extract SET id={val} WHERE id = {e}")  # will cascade
            if val >= max_extract:
                list(db.execute(
                    f"SELECT setval('extract_id_seq'::regclass, {max_extract})"))
        errors = list(db.execute(
            """SELECT count(id) FROM idea_content_link
            WHERE extract_id IS NOT NULL AND extract_id != id"""))[0][0]
        assert not errors
        mark_changed()

    with context.begin_transaction():
        op.create_table(
            'idea_content_positive_link',
            sa.Column('id', sa.Integer, sa.ForeignKey(
                'idea_content_link.id',
                ondelete='CASCADE', onupdate='CASCADE'
            ), primary_key=True)
        )
        op.create_table(
            'idea_content_widget_link',
            sa.Column('id', sa.Integer, sa.ForeignKey(
                'idea_content_positive_link.id',
                ondelete='CASCADE', onupdate='CASCADE'
            ), primary_key=True)
        )
        op.create_table(
            'idea_related_post_link',
            sa.Column('id', sa.Integer, sa.ForeignKey(
                'idea_content_positive_link.id',
                ondelete='CASCADE', onupdate='CASCADE'
            ), primary_key=True)
        )
        op.create_table(
            'idea_content_negative_link',
            sa.Column('id', sa.Integer, sa.ForeignKey(
                'idea_content_link.id',
                ondelete='CASCADE', onupdate='CASCADE'
            ), primary_key=True)
        )
        op.create_table(
            'idea_thread_context_break_link',
            sa.Column('id', sa.Integer, sa.ForeignKey(
                'idea_content_negative_link.id',
                ondelete='CASCADE', onupdate='CASCADE'
            ), primary_key=True)
        )
        op.execute(
            """INSERT INTO idea_content_positive_link
            (SELECT id FROM idea_content_link WHERE type IN (
                'assembl:postLinkedToIdea_abstract',
                'assembl:postHiddenLinkedToIdea',
                'assembl:postLinkedToIdea',
                'assembl:postExtractRelatedToIdea'))""")
        op.execute(
            """INSERT INTO idea_content_widget_link
            (SELECT id FROM idea_content_link
            WHERE type = 'assembl:postHiddenLinkedToIdea')""")
        op.execute(
            """INSERT INTO idea_related_post_link
            (SELECT id FROM idea_content_link
            WHERE type = 'assembl:postLinkedToIdea')""")
        op.execute(
            """INSERT INTO idea_content_negative_link
            (SELECT id FROM idea_content_link WHERE type IN (
                'assembl:postDelinkedToIdea_abstract',
                'assembl:postDelinkedToIdea'))""")
        op.execute(
            """INSERT INTO idea_content_negative_link
            (SELECT id FROM idea_content_link WHERE type IN (
                'assembl:postDelinkedToIdea_abstract',
                'assembl:postDelinkedToIdea'))""")
        op.execute(
            """INSERT INTO idea_thread_context_break_link
            (SELECT id FROM idea_content_link
            WHERE type = 'assembl:postDelinkedToIdea')""")

        op.alter_column('extract', 'id', server_default=None)
        op.add_column('extract', sa.Column(
            'owner_id', sa.Integer, sa.ForeignKey('agent_profile.id')))
        op.execute('UPDATE extract SET owner_id=creator_id')
        op.alter_column('extract', 'owner_id', nullable=False)
        op.drop_column('extract', 'creator_id')  # losing information
        op.drop_column('extract', 'creation_date')  # losing information
        op.drop_column('extract', 'content_id')  # should match icl... assert?
        op.execute("drop sequence extract_id_seq")
        op.create_foreign_key(
            'extract_id_fkey', 'extract', 'idea_content_positive_link',
            ['id'], ['id'], ondelete='CASCADE', onupdate='CASCADE')
        op.drop_column('idea_content_link', 'extract_id')
        op.drop_constraint('idea_content_link_idea_id_fkey', 'idea_content_link')
        op.create_foreign_key(
            'idea_content_link_idea_id_fkey', 'idea_content_link', 'idea',
            ['idea_id'], ['id'])
