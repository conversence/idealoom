"""idea and idealink types

Revision ID: d9c8dbb4dcc6
Revises: 693170d95790
Create Date: 2017-09-14 17:52:26.781960

"""

# revision identifiers, used by Alembic.
revision = 'd9c8dbb4dcc6'
down_revision = '693170d95790'

from alembic import context, op
import sqlalchemy as sa
import transaction

from assembl.lib.sqla import mark_changed
from assembl.semantic import jsonld_context
from assembl.lib import config


def upgrade(pyramid_env):
    from assembl import models as m
    db = m.get_session_maker()()
    with transaction.manager:
        m.URIRefDb.populate_db(db)
        mark_changed()

    with context.begin_transaction():
        op.add_column('idea', sa.Column(
            'rdf_type_id', sa.Integer,
            sa.ForeignKey('uriref.id'), server_default='1'))
        op.add_column('idea_idea_link', sa.Column(
            'rdf_type_id', sa.Integer,
            sa.ForeignKey('uriref.id'), server_default='2'))

    # Do stuff with the app's models here.
    with transaction.manager:
        m.URIRefDb.populate_db(db)
        different = list(db.execute(
            """SELECT id, rdf_type FROM idea
            WHERE rdf_type != 'idea:GenericIdeaNode'"""))
        if different:
            ctx = jsonld_context()
            missing = [{"id": id, "rdf_type_id": m.URIRefDb.get_or_create(
                            ctx.expand(rdf_type)).id}
                        for id, rdf_type in different]
            db.bulk_update_mappings(m.Idea.__mapper__, missing)
            mark_changed()
        different = list(db.execute(
            """SELECT id, rdf_type FROM idea_idea_link
            WHERE rdf_type != 'idea:InclusionRelation'"""))
        if different:
            ctx = jsonld_context()
            missing = [{"id": id, "rdf_type_id": m.URIRefDb.get_or_create(
                            ctx.expand(rdf_type)).id}
                        for id, rdf_type in different]
            db.bulk_update_mappings(m.IdeaLink.__mapper__, missing)
            mark_changed()

    with context.begin_transaction():
        op.drop_column('idea', 'rdf_type')
        op.drop_column('idea_idea_link', 'rdf_type')


def downgrade(pyramid_env):
    with context.begin_transaction():
        op.add_column('idea', sa.Column(
            'rdf_type', sa.String(60), nullable=False,
            server_default='idea:GenericIdeaNode'))
        op.add_column('idea_idea_link', sa.Column(
            'rdf_type', sa.String(60), nullable=False,
            server_default='idea:InclusionRelation'))

    # Do stuff with the app's models here.
    from assembl import models as m
    db = m.get_session_maker()()
    with transaction.manager:
        different = list(db.execute(
            """SELECT idea.id, uriref.val FROM idea
            JOIN uriref ON (rdf_type_id=uriref.id)
            WHERE idea.rdf_type_id != 1"""))
        db.execute("UPDATE idea SET rdf_type_id=3 WHERE sqla_type='root_idea'")
        if different:
            ctx = jsonld_context()
            missing = [{"id": id, "rdf_type": ctx.shrink_iri(uri)}
                        for id, uri in different]
            db.bulk_update_mappings(m.Idea.__mapper__, missing)
            mark_changed()
        different = list(db.execute(
            """SELECT idea_idea_link.id, uriref.val FROM idea_idea_link
            JOIN uriref ON (rdf_type_id=uriref.id)
            WHERE idea_idea_link.rdf_type_id != 2"""))
        if different:
            ctx = jsonld_context()
            missing = [{"id": id, "rdf_type": ctx.shrink_iri(uri)}
                        for id, uri in different]
            db.bulk_update_mappings(m.IdeaLink.__mapper__, missing)
            mark_changed()

    with context.begin_transaction():
        op.drop_column('idea', 'rdf_type_id')
        op.drop_column('idea_idea_link', 'rdf_type_id')
