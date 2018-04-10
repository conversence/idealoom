"""annotation polymorphism

Revision ID: d1d922f0cf3a
Revises: e7b56b85b1f5
Create Date: 2018-04-05 15:52:16.181723

"""

# revision identifiers, used by Alembic.
revision = 'd1d922f0cf3a'
down_revision = 'e7b56b85b1f5'

from alembic import context, op
import sqlalchemy as sa
import transaction


from assembl.lib import config


def upgrade(pyramid_env):
    with context.begin_transaction():
        op.create_table(
            'annotation_selector',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('extract_id', sa.Integer, sa.ForeignKey(
                'extract.id', onupdate="CASCADE", ondelete="CASCADE"),
                nullable=False, index=True),
            sa.Column('type', sa.String(60)),
            sa.Column('refines_id', sa.Integer, sa.ForeignKey(
                'annotation_selector.id', ondelete="CASCADE"))
        )
        op.execute('''
            INSERT INTO annotation_selector (id, extract_id, type)
            SELECT id, extract_id, 'AnnotatorRange'
            FROM text_fragment_identifier''')
        op.create_foreign_key(
            "text_fragment_identifier_id_fkey", "text_fragment_identifier",
            "annotation_selector", ["id"], ["id"],
            onupdate="CASCADE", ondelete="CASCADE")
        op.drop_column('text_fragment_identifier', 'extract_id')

    from assembl import models as m
    db = m.get_session_maker()()
    with transaction.manager:
        (maxid,) = db.query('max(id) from annotation_selector').first()
        db.query("setval('annotation_selector_id_seq'::regclass, %d)" % (maxid,)).first()


def downgrade(pyramid_env):
    with context.begin_transaction():
        op.add_column(
            'text_fragment_identifier',
            sa.Column('extract_id', sa.Integer, sa.ForeignKey(
                'extract.id', onupdate="CASCADE", ondelete="CASCADE"),
                index=True))
        op.execute('''
            UPDATE text_fragment_identifier tfi
            SET (extract_id) = (
                SELECT extract_id FROM annotation_selector sel
                WHERE sel.id = tfi.id)''')
        op.alter_column('text_fragment_identifier', 'extract_id', nullable=False)
        op.drop_constraint(
            "text_fragment_identifier_id_fkey", "text_fragment_identifier")
        op.drop_table('annotation_selector')
