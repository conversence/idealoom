"""Models for widgets, a set of bundled functionality.

In theory, arbitrary widgets could be added to IdeaLoom.
In reality, the set of widget behaviours is constrained here.
"""
from itertools import chain
from datetime import datetime
import logging

from sqlalchemy import (
    Column, Integer, ForeignKey, Text, String, Boolean, DateTime, inspect)
from sqlalchemy.sql import text, column
from sqlalchemy.orm import (
    relationship, backref, aliased, join)
from sqlalchemy.ext.associationproxy import association_proxy
import simplejson as json

from assembl.lib.parsedatetime import parse_datetime
from ..auth import (
    CrudPermissions, Everyone, P_ADD_IDEA, P_READ, P_EDIT_IDEA,
    P_ADD_POST, P_ADMIN_DISC)
from ..lib.sqla_types import URLString
from . import DiscussionBoundBase
from .discussion import Discussion
from .idea import (Idea, IdeaLink)
from .idea_content_link import IdeaContentWidgetLink
from .generic import Content
from .post import Post, IdeaProposalPost
from .auth import User
from .votes import AbstractVoteSpecification, AbstractIdeaVote
from ..views.traversal import (
    RelationCollectionDefinition, AbstractCollectionDefinition,
    collection_creation_side_effects, InstanceContext)
from ..semantic.virtuoso_mapping import QuadMapPatternS
from ..semantic.namespaces import (ASSEMBL, QUADNAMES)


log = logging.getLogger(__name__)


class Widget(DiscussionBoundBase):
    __tablename__ = "widget"

    id = Column(Integer, primary_key=True)

    type = Column(String(60), nullable=False)

    __mapper_args__ = {
        'polymorphic_identity': 'widget',
        'polymorphic_on': 'type',
        'with_polymorphic': '*'
    }

    settings = Column(Text)  # JSON blob
    state = Column(Text)  # JSON blob

    discussion_id = Column(
        Integer,
        ForeignKey('discussion.id', ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False, index=True
    )
    discussion = relationship(
        Discussion, backref=backref("widgets", cascade="all, delete-orphan"),
        info={'rdf': QuadMapPatternS(None, ASSEMBL.in_conversation)})

    start_date = Column(DateTime, server_default=None)
    end_date = Column(DateTime, server_default=None)
    hide_notification = Column(Boolean, server_default='false', default=False)

    def __init__(self, *args, **kwargs):
        super(Widget, self).__init__(*args, **kwargs)
        self.interpret_settings(self.settings_json)

    def interpret_settings(self, settings):
        pass

    def populate_from_context(self, context):
        if not(self.discussion or self.discussion_id):
            self.discussion = context.get_instance_of_class(Discussion)
        super(Widget, self).populate_from_context(context)

    def get_discussion_id(self):
        return self.discussion_id

    @classmethod
    def get_discussion_conditions(cls, discussion_id, alias_maker=None):
        return (cls.discussion_id == discussion_id,)

    @classmethod
    def get_ui_endpoint_base(cls):
        # TODO: Make this configurable.
        return None

    @property
    def configured(self):
        return True

    def get_ui_endpoint(self):
        uri = self.get_ui_endpoint_base()
        assert uri
        return "%s?config=%s" % (uri, self.uri())

    def get_user_state_url(self):
        return 'local:Widget/%d/user_state' % (self.id,)

    def get_settings_url(self):
        return 'local:Widget/%d/settings' % (self.id,)

    def get_state_url(self):
        return 'local:Widget/%d/state' % (self.id,)

    def get_user_states_url(self):
        return 'local:Widget/%d/user_states' % (self.id,)

    # Eventually: Use extra_columns to get WidgetUserConfig
    # through user_id instead of widget_user_config.id

    @property
    def settings_json(self):
        if self.settings:
            settings = json.loads(self.settings)
            # Do not allow non-dict settings
            if isinstance(settings, dict):
                return settings
        return {}

    @settings_json.setter
    def settings_json(self, val):
        self.settings = json.dumps(val)
        self.interpret_settings(val)

    @property
    def state_json(self):
        if self.state:
            return json.loads(self.state)
        return {}

    @state_json.setter
    def state_json(self, val):
        self.state = json.dumps(val)

    def get_user_state(self, user_id):
        state = self.db.query(WidgetUserConfig).filter_by(
            widget=self, user_id=user_id).first()
        if state:
            return state.state_json

    def get_all_user_states(self):
        return [c.state_json for c in self.user_configs]

    def set_user_state(self, user_state, user_id):
        state = self.db.query(WidgetUserConfig).filter_by(
            widget=self, user_id=user_id).first()
        if not state:
            state = WidgetUserConfig(widget=self, user_id=user_id)
            self.db.add(state)
        state.state_json = user_state

    def update_from_json(self, json, user_id=None, context=None, object_importer=None,
                         permissions=None, parse_def_name='default_reverse'):
        modified = super(Widget, self).update_from_json(
            json, user_id, context, object_importer, permissions, parse_def_name)

        if user_id and user_id != Everyone and 'user_state' in json:
            modified.set_user_state(json['user_state'], user_id)
        return modified

    @classmethod
    def filter_started(cls, query):
        return query.filter(
            (cls.start_date == None) | (cls.start_date <= datetime.utcnow()))

    @classmethod
    def test_active(cls):
        now = datetime.utcnow()
        return ((cls.end_date == None) | (cls.end_date > now)
                & (cls.start_date == None) | (cls.start_date <= now))

    @classmethod
    def filter_active(cls, query):
        return query.filter(cls.test_active())

    def is_started(self):
        return self.start_date == None or self.start_date <= datetime.utcnow()

    def is_ended(self):
        return self.end_date != None and self.end_date < datetime.utcnow()

    def is_active(self):
        return self.is_started() and not self.is_ended()

    @property
    def activity_state(self):
        # TODO: Convert to enum
        if not self.is_started():
            return "not started"
        if self.is_ended():
            return "ended"
        return "active"

    @classmethod
    def test_ended(cls):
        return (cls.end_date != None) | (cls.end_date < datetime.utcnow())

    crud_permissions = CrudPermissions(P_ADMIN_DISC)

    def notification_data(self, notification_setting_data):
        pass

    def has_notification(self):
        settings = self.settings_json
        notifications = settings.get('notifications', [])
        now = datetime.utcnow()

        for notification in notifications:
            try:
                start = parse_datetime(notification['start'])
                end = notification.get('end', None)
                end = parse_datetime(end) if end else datetime.max
                if now < start or now > end:
                    continue
            except (ValueError, TypeError, KeyError) as e:
                continue
            notification_data = self.notification_data(notification)
            if notification_data:
                yield notification_data


class IdeaWidgetLink(DiscussionBoundBase):
    __tablename__ = 'idea_widget_link'

    id = Column(Integer, primary_key=True,
                info={'rdf': QuadMapPatternS(None, ASSEMBL.db_id)})
    type = Column(String(60))

    idea_id = Column(Integer, ForeignKey(Idea.id),
                     nullable=False, index=True)
    idea = relationship(
        Idea, primaryjoin=(Idea.id == idea_id),
        backref=backref("widget_links", cascade="all, delete-orphan"))

    widget_id = Column(Integer, ForeignKey(
        Widget.id, ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False, index=True)
    widget = relationship(Widget, backref=backref(
        'idea_links', cascade="all, delete-orphan"))

    context_url = Column(URLString())

    __mapper_args__ = {
        'polymorphic_identity': 'abstract_idea_widget_link',
        'polymorphic_on': type,
        'with_polymorphic': '*'
    }

    def populate_from_context(self, context):
        if not(self.widget or self.widget_id):
            self.widget = context.get_instance_of_class(Widget)
        if not(self.idea or self.idea_id):
            self.idea = context.get_instance_of_class(Idea)
        super(IdeaWidgetLink, self).populate_from_context(context)

    def get_discussion_id(self):
        idea = self.idea or Idea.get(self.idea_id)
        return idea.get_discussion_id()

    @classmethod
    def get_discussion_conditions(cls, discussion_id, alias_maker=None):
        return ((cls.idea_id == Idea.id),
                (Idea.discussion_id == discussion_id))

    discussion = relationship(
        Discussion, viewonly=True, uselist=False, secondary=Idea.__table__,
        info={'rdf': QuadMapPatternS(None, ASSEMBL.in_conversation)})

    crud_permissions = CrudPermissions(
        P_ADD_IDEA, P_READ, P_EDIT_IDEA, P_EDIT_IDEA,
        P_EDIT_IDEA, P_EDIT_IDEA)


# Note: declare all subclasses of IdeaWidgetLink here,
# so we can use polymorphic_filter later.


def PolymorphicMixinFactory(base_class):
    """A factory for PolymorphicMixin marker classes"""
    class PolymorphicMixin(object):
        "A marker class that provides polymorphic_filter"
        @classmethod
        def polymorphic_identities(cls):
            "Return the list of polymorphic identities defined in subclasses"
            return [k for (k, v)
                    in base_class.__mapper__.polymorphic_map.items()
                    if issubclass(v.class_, cls)]

        @classmethod
        def polymorphic_filter(cls):
            "Return a SQLA expression that tests for subclasses of this class"
            return base_class.__mapper__.polymorphic_on.in_(
                cls.polymorphic_identities())
    return PolymorphicMixin


class BaseIdeaWidgetLink(IdeaWidgetLink):
    __mapper_args__ = {
        'polymorphic_identity': 'base_idea_widget_link',
    }


class GeneratedIdeaWidgetLink(IdeaWidgetLink):
    __mapper_args__ = {
        'polymorphic_identity': 'generated_idea_widget_link',
    }


IdeaShowingWidgetLink = PolymorphicMixinFactory(
    IdeaWidgetLink)


IdeaDescendantsShowingWidgetLink = PolymorphicMixinFactory(
    IdeaWidgetLink)


class IdeaInspireMeWidgetLink(
        IdeaDescendantsShowingWidgetLink, BaseIdeaWidgetLink):
    __mapper_args__ = {
        'polymorphic_identity': 'idea_inspire_me_widget_link',
    }



class IdeaCreativitySessionWidgetLink(
        IdeaShowingWidgetLink, BaseIdeaWidgetLink):
    __mapper_args__ = {
        'polymorphic_identity': 'idea_creativity_session_widget_link',
    }


class VotableIdeaWidgetLink(IdeaShowingWidgetLink, IdeaWidgetLink):
    __mapper_args__ = {
        'polymorphic_identity': 'votable_idea_widget_link',
    }


class VotedIdeaWidgetLink(IdeaWidgetLink):
    __mapper_args__ = {
        'polymorphic_identity': 'voted_idea_widget_link',
    }


class VotingCriterionWidgetLink(IdeaWidgetLink):
    __mapper_args__ = {
        'polymorphic_identity': 'criterion_widget_link',
    }


# Then declare relationships

Idea.widgets = association_proxy('widget_links', 'widget')

Widget.showing_idea_links = relationship(
    IdeaWidgetLink,
    primaryjoin=((Widget.id == IdeaWidgetLink.widget_id)
                 & IdeaShowingWidgetLink.polymorphic_filter()))
Idea.has_showing_widget_links = relationship(
    IdeaWidgetLink,
    primaryjoin=((Idea.id == IdeaWidgetLink.idea_id)
                 & IdeaShowingWidgetLink.polymorphic_filter()))

Widget.showing_ideas = relationship(
    Idea, viewonly=True, secondary=IdeaWidgetLink.__table__,
    primaryjoin=((Widget.id == IdeaWidgetLink.widget_id)
                 & IdeaShowingWidgetLink.polymorphic_filter()),
    secondaryjoin=IdeaWidgetLink.idea_id == Idea.id,
    backref='showing_widget')


Idea.active_showing_widget_links = relationship(
    IdeaWidgetLink, viewonly=True,
    primaryjoin=((IdeaWidgetLink.idea_id == Idea.id)
                 & IdeaShowingWidgetLink.polymorphic_filter()
                 & (IdeaWidgetLink.widget_id == Widget.id)
                 & Widget.test_active()))


class BaseIdeaWidget(Widget):
    """A widget attached to a :py:class:`assembl.models.idea.Idea`, its ``base_idea``"""
    __mapper_args__ = {
        'polymorphic_identity': 'idea_view_widget',
    }

    base_idea_link = relationship(BaseIdeaWidgetLink, uselist=False)
    base_idea_link_class = BaseIdeaWidgetLink

    def interpret_settings(self, settings):
        if 'idea' in settings:
            self.set_base_idea_id(Idea.get_database_id(settings['idea']))

    def base_idea_id(self):
        if self.base_idea_link:
            return self.base_idea_link.idea_id

    def set_base_idea_id(self, id):
        idea = Idea.get_instance(id)
        if self.base_idea_link:
            self.base_idea_link.idea_id = id
        else:
            self.base_idea_link = self.base_idea_link_class(
                widget=self, idea=idea)
            self.db.add(self.base_idea_link)
        # This is wrong, but not doing it fails.
        self.base_idea = idea

    def get_ideas_url(self):
        return 'local:Conversation/%d/widgets/%d/base_idea/-/children' % (
            self.discussion_id, self.id)

    def get_messages_url(self):
        return 'local:Conversation/%d/widgets/%d/base_idea/-/widgetposts' % (
            self.discussion_id, self.id)

    @classmethod
    def extra_collections(cls):
        return (BaseIdeaCollection(),
                BaseIdeaDescendantsCollection('base_idea_descendants'))


BaseIdeaWidget.base_idea = relationship(
        Idea, viewonly=True, secondary=BaseIdeaWidgetLink.__table__,
        primaryjoin=((BaseIdeaWidget.id == BaseIdeaWidgetLink.widget_id)
                     & BaseIdeaWidgetLink.polymorphic_filter()),
        secondaryjoin=BaseIdeaWidgetLink.idea_id == Idea.id,
        uselist=False)


class BaseIdeaCollection(RelationCollectionDefinition):
    """The 'collection' of the ``base_idea`` of this :py:class:`BaseIdeaWidget`"""
    def __init__(self, name=None):
        super(BaseIdeaCollection, self).__init__(
            BaseIdeaWidget, BaseIdeaWidget.base_idea, name)

    def decorate_query(self, query, owner_alias, last_alias, parent_instance, ctx):
        widget = owner_alias
        idea = last_alias
        return query.join(
            BaseIdeaWidgetLink,
            idea.id == BaseIdeaWidgetLink.idea_id).join(
                widget).filter(widget.id == parent_instance.id).filter(
                    widget.id == BaseIdeaWidgetLink.widget_id,
                    BaseIdeaWidgetLink.polymorphic_filter())


class BaseIdeaDescendantsCollection(AbstractCollectionDefinition):
    """The collection of the descendants of the ``base_idea`` of this :py:class:`BaseIdeaWidget`"""

    def __init__(self, name):
        super(BaseIdeaDescendantsCollection, self).__init__(
            BaseIdeaWidget, name, Idea)

    def decorate_query(self, query, owner_alias, last_alias, parent_instance, ctx):
        widget = owner_alias
        descendant = last_alias
        link = parent_instance.base_idea_link
        if link:
            descendants_subq = link.idea.get_descendants_query()
            query = query.filter(
                descendant.id.in_(descendants_subq)).join(
                widget, widget.id == parent_instance.id)
        return query

    def contains(self, parent_instance, instance):
        descendant = aliased(Idea, name="descendant")
        link = parent_instance.base_idea_link
        if link:
            descendants_subq = link.idea.get_descendants_query()
            query = instance.db.query(descendant).filter(
                descendant.id.in_(descendants_subq)).join(
                Widget, Widget.id == parent_instance.id)
        return query.count() > 0


class IdeaCreatingWidget(BaseIdeaWidget):
    """A widget where new ideas are created"""
    __mapper_args__ = {
        'polymorphic_identity': 'idea_creating_widget',
    }

    generated_idea_links = relationship(GeneratedIdeaWidgetLink)

    def get_confirm_ideas_url(self):
        idea_uri = self.settings_json.get('idea', None)
        if idea_uri:
            return ('local:Conversation/%d/widgets/%d/confirm_ideas') % (
                self.discussion_id, self.id)

    def get_confirm_messages_url(self):
        idea_uri = self.settings_json.get('idea', None)
        if idea_uri:
            return ('local:Conversation/%d/widgets/%d/confirm_messages') % (
                self.discussion_id, self.id)

    def get_confirmed_ideas(self):
        # TODO : optimize
        return [idea.uri() for idea in self.generated_ideas if not idea.hidden]

    def get_num_ideas(self):
        return len(self.generated_idea_links)

    def set_confirmed_ideas(self, idea_ids):
        for idea in self.generated_ideas:
            uri = idea.uri()
            hide = uri not in idea_ids
            idea.hidden = hide
            # p = idea.proposed_in_post
            # if p:
            #     p.hidden = hide

    def get_confirmed_messages(self):
        root_idea_id = self.base_idea_id()
        ids = self.db.query(Content.id).join(
            IdeaContentWidgetLink).join(
            Idea, IdeaContentWidgetLink.idea_id == Idea.id).join(
            IdeaLink, IdeaLink.target_id == Idea.id).filter(
            IdeaLink.source_id == root_idea_id, ~Content.hidden
            ).union(
                self.db.query(IdeaProposalPost.id).join(
                    Idea, IdeaProposalPost.idea_id == Idea.id).join(
                    IdeaLink, IdeaLink.target_id == Idea.id).filter(
                    IdeaLink.source_id == root_idea_id,
                    ~IdeaProposalPost.hidden)
            ).all()
        return [Content.uri_generic(id) for (id,) in ids]

    def set_confirmed_messages(self, post_ids):
        root_idea_id = self.base_idea_id()
        for post in self.db.query(Content).join(
                IdeaContentWidgetLink).join(
                Idea, IdeaContentWidgetLink.idea_id == Idea.id).join(
                IdeaLink, IdeaLink.target_id == Idea.id).filter(
                IdeaLink.source_id == root_idea_id).all():
            post.hidden = (post.uri() not in post_ids)
        for post in self.db.query(IdeaProposalPost).join(
                Idea, IdeaProposalPost.idea_id == Idea.id).join(
                IdeaLink, IdeaLink.target_id == Idea.id).filter(
                IdeaLink.source_id == root_idea_id).all():
            post.hidden = (post.uri() not in post_ids)

    def get_ideas_hiding_url(self):
        return 'local:Conversation/%d/widgets/%d/base_idea_hiding/-/children' % (
            self.discussion_id, self.id)

    @classmethod
    def extra_collections(cls):
        class BaseIdeaCollectionC(BaseIdeaCollection):
            """The BaseIdeaCollection for an IdeaCreatingWidget"""
            hide_proposed_ideas = False

            def decorate_query(self, query, owner_alias, last_alias, parent_instance, ctx):
                query = super(BaseIdeaCollectionC, self).decorate_query(
                    query, owner_alias, last_alias, parent_instance, ctx)
                children_ctx = ctx.find_collection('Idea.children')
                if children_ctx:
                    gen_idea_link = aliased(GeneratedIdeaWidgetLink)
                    query = query.join(
                        gen_idea_link,
                        (gen_idea_link.idea_id ==
                            children_ctx.class_alias.id) & (
                        gen_idea_link.widget_id == owner_alias.id))
                return query

        class BaseIdeaHidingCollection(BaseIdeaCollectionC):
            """The BaseIdeaCollection for an IdeaCreatingWidget, which will hide
            created ideas."""
            hide_proposed_ideas = True

            def extra_permissions(self, permissions):
                """permission loophoole: allow participants (someone with the ADD_POST
                permission) to create (hidden) ideas in this context."""
                if P_ADD_POST in permissions and P_ADD_IDEA not in permissions:
                    return [P_ADD_IDEA]
                return []


        class BaseIdeaDescendantsCollectionC(BaseIdeaDescendantsCollection):
            hide_proposed_ideas = False

            def decorate_query(self, query, owner_alias, last_alias, parent_instance, ctx):
                query = super(BaseIdeaDescendantsCollectionC, self).decorate_query(
                    query, owner_alias, last_alias, parent_instance, ctx)
                children_ctx = ctx.find_collection(
                    'Idea.children')
                if children_ctx:
                    gen_idea_link = aliased(GeneratedIdeaWidgetLink)
                    query = query.join(
                        gen_idea_link,
                        (gen_idea_link.idea_id ==
                            children_ctx.class_alias.id))
                return query

        @collection_creation_side_effects.register(
            inst_ctx=Idea, ctx='IdeaCreatingWidget.base_idea')
        @collection_creation_side_effects.register(
            inst_ctx=Idea, ctx='IdeaCreatingWidget.base_idea_descendants')
        def add_proposal_post(inst_ctx, ctx):
            from .langstrings import LangString
            obj = inst_ctx._instance
            yield InstanceContext(
                inst_ctx['proposed_in_post'],
                IdeaProposalPost(
                    proposes_idea=obj,
                    creator=ctx.get_instance_of_class(User),
                    discussion=obj.discussion,
                    subject=(obj.short_title.clone()
                             if obj.short_title
                             else LangString.EMPTY(obj.db)),
                    body=(obj.definition.clone()
                          if obj.definition
                          else LangString.EMPTY(obj.db))))
            yield InstanceContext(
                inst_ctx['widget_links'],
                GeneratedIdeaWidgetLink(
                    idea=obj,
                    widget=ctx.get_instance_of_class(IdeaCreatingWidget)))

        @collection_creation_side_effects.register(
            inst_ctx=IdeaProposalPost, ctx='BaseIdeaWidget.base_idea')
        @collection_creation_side_effects.register(
            inst_ctx=IdeaProposalPost,
            ctx='IdeaCreatingWidget.base_idea_descendants')
        def add_proposal_post_link(inst_ctx, ctx):
            obj = inst_ctx._instance
            yield InstanceContext(
                inst_ctx['idea_links_of_content'],
                IdeaContentWidgetLink(
                    content=obj, idea=obj.proposes_idea,
                    creator=obj.creator))

        @collection_creation_side_effects.register(
            inst_ctx=Idea, ctx='BaseIdeaWidget.base_idea_hiding')
        def hide_proposal_idea(inst_ctx, ctx):
            obj = inst_ctx._instance
            obj.hidden = True
            for subctx in add_proposal_post(inst_ctx, ctx):
                yield subctx

        @collection_creation_side_effects.register(
            inst_ctx=IdeaProposalPost, ctx='BaseIdeaWidget.base_idea_hiding')
        def hide_proposal_post(inst_ctx, ctx):
            obj = inst_ctx._instance
            obj.hidden = True
            for subctx in add_proposal_post_link(inst_ctx, ctx):
                yield subctx

        return (BaseIdeaCollectionC(),
                BaseIdeaHidingCollection('base_idea_hiding'),
                BaseIdeaDescendantsCollectionC('base_idea_descendants'))


IdeaCreatingWidget.generated_ideas = relationship(
    Idea, viewonly=True, secondary=GeneratedIdeaWidgetLink.__table__,
    primaryjoin=((IdeaCreatingWidget.id == GeneratedIdeaWidgetLink.widget_id)
                 & GeneratedIdeaWidgetLink.polymorphic_filter()),
    secondaryjoin=GeneratedIdeaWidgetLink.idea_id == Idea.id)


class InspirationWidget(IdeaCreatingWidget):
    default_view = 'creativity_widget'
    __mapper_args__ = {
        'polymorphic_identity': 'inspiration_widget',
    }
    base_idea_link_class = IdeaInspireMeWidgetLink

    @property
    def configured(self):
        active_modules = self.settings_json.get('active_modules', {})
        return bool(active_modules.get('card', None)
                or active_modules.get('video', None))

    @classmethod
    def get_ui_endpoint_base(cls):
        # TODO: Make this configurable.
        return "/static/widget/creativity/"

    def get_add_post_endpoint(self, idea):
        return 'local:Conversation/%d/widgets/%d/base_idea_descendants/%d/linkedposts' % (
            self.discussion_id, self.id, idea.id)


class CreativitySessionWidget(IdeaCreatingWidget):
    default_view = 'creativity_widget'
    __mapper_args__ = {
        'polymorphic_identity': 'creativity_session_widget',
    }

    @classmethod
    def get_ui_endpoint_base(cls):
        # TODO: Make this configurable.
        return "/static/widget/session/#home"

    def set_base_idea_id(self, id):
        idea = Idea.get_instance(id)
        if self.base_idea_link:
            self.base_idea_link.idea_id = id
        else:
            self.base_idea_link = IdeaCreativitySessionWidgetLink(widget=self, idea=idea)
            self.db.add(self.base_idea_link)
        # This is wrong, but not doing it fails.
        self.base_idea = idea

    def notification_data(self, data):
        end = data.get('end', None)
        time_to_end = (parse_datetime(end) - datetime.utcnow()
                       ).total_seconds() if end else None
        return dict(
            data,
            widget_url=self.uri(),
            time_to_end=time_to_end,
            num_participants=self.num_participants(),
            num_ideas=len(self.generated_idea_links))

    def num_participants(self):
        participant_ids = set()
        # participants from user_configs
        participant_ids.update((c.user_id for c in self.user_configs))
        # Participants from comments
        participant_ids.update((c[0] for c in self.db.query(
            Post.creator_id).join(IdeaContentWidgetLink).filter(
                Widget.id == self.id)))
        # Participants from created ideas
        participant_ids.update((c[0] for c in self.db.query(
            IdeaProposalPost.creator_id).join(
                Idea, GeneratedIdeaWidgetLink).filter(
                    Widget.id == self.id)))
        return len(participant_ids)

    def num_posts_by(self, user_id):
        from .post import WidgetPost
        return self.db.query(WidgetPost
            ).join(self.__class__
            ).filter(WidgetPost.creator_id==user_id).count()

    @property
    def num_posts_by_current_user(self):
        from ..auth.util import get_current_user_id
        user_id = get_current_user_id()
        if user_id:
            return self.num_posts_by(user_id)

    def get_add_post_endpoint(self, idea):
        return 'local:Conversation/%d/widgets/%d/base_idea/-/children/%d/widgetposts' % (
            self.discussion_id, self.id, idea.id)


class VotingWidget(BaseIdeaWidget):
    default_view = 'voting_widget'
    __mapper_args__ = {
        'polymorphic_identity': 'voting_widget',
    }

    votable_idea_links = relationship(VotableIdeaWidgetLink)
    voted_idea_links = relationship(VotedIdeaWidgetLink)
    criteria_links = relationship(
        VotingCriterionWidgetLink, backref="voting_widget")

    @classmethod
    def get_ui_endpoint_base(cls):
        # TODO: Make this configurable.
        return "/static/widget/vote/"

    def interpret_settings(self, settings):
        if "idea" not in settings and "votable_root_id" in settings:
            settings["idea"] = settings["votable_root_id"]
        super(VotingWidget, self).interpret_settings(settings)
        if 'criteria' in settings:
            for criterion in settings['criteria']:
                try:
                    criterion_idea = Idea.get_instance(criterion["@id"])
                    self.add_criterion(criterion_idea)
                except Exception as e:
                    log.error("Missing criterion. Discarded. " + criterion)
        if 'votables' in settings:
            for votable_id in settings['votables']:
                try:
                    votable_idea = Idea.get_instance(votable_id)
                    self.add_votable(votable_idea)
                except Exception as e:
                    log.error("Missing votable. Discarded. " + votable_id)
        elif 'votable_root_id' in settings:
            try:
                votable_root_idea = Idea.get_instance(
                    settings['votable_root_id'])
            except Exception as e:
                log.error("Cannot find votable root. " + settings['votable_root_id'])
                return
            if len(votable_root_idea.children):
                for child in votable_root_idea.children:
                    self.add_votable(child)
            else:
                self.add_votable(votable_root_idea)

    @property
    def criteria_url(self):
        return 'local:Conversation/%d/widgets/%d/criteria' % (
            self.discussion_id, self.id)

    @property
    def votespecs_url(self):
        return 'local:Conversation/%d/widgets/%d/vote_specifications' % (
            self.discussion_id, self.id)

    @property
    def votables_url(self):
        return 'local:Conversation/%d/widgets/%d/targets/' % (
            self.discussion_id, self.id)

    def get_user_votes_url(self, idea_id):
        return 'local:Conversation/%d/widgets/%d/targets/%d/votes' % (
            self.discussion_id, self.id, Idea.get_database_id(idea_id))

    def all_voting_results(self):
        return {
            spec.uri(): spec.voting_results()
            for spec in self.vote_specifications
        }

    def get_voting_urls(self, target_idea_id):
        # TODO: Does not work yet.
        return {
            AbstractVoteSpecification.uri_generic(vote_spec.id):
            'local:Conversation/%d/widgets/%d/vote_specifications/%d/vote_targets/%d/votes' % (
                self.discussion_id, self.id, vote_spec.id,
                Idea.get_database_id(target_idea_id))
            for vote_spec in self.vote_specifications
        }

    def get_voting_results_by_spec_url(self):
        return {
            AbstractVoteSpecification.uri_generic(vote_spec.id):
            'local:Conversation/%d/widgets/%d/vote_specifications/%d/vote_results' % (
                self.discussion_id, self.id, vote_spec.id)
            for vote_spec in self.vote_specifications
        }


    def add_criterion(self, idea):
        if idea not in self.criteria:
            self.criteria_links.append(VotingCriterionWidgetLink(
                widget=self, idea=idea))

    def remove_criterion(self, idea):
        for link in self.criteria_links:
            if link.idea == idea:
                self.criteria_links.remove(link)
                return

    @property
    def configured(self):
        if not bool(len(self.votable_idea_links)
                    and len(self.vote_specifications)):
            return False
        items = self.settings_json.get('items', ())
        return bool(len(
            [item for item in items
             if item.get('vote_specifications', None)]))

    def set_criteria(self, ideas):
        idea_ids = {idea.id for idea in ideas}
        for link in list(self.criteria_links):
            if link.idea_id not in idea_ids:
                self.criteria_links.remove(link)
                self.db.delete(link)
            else:
                idea_ids.remove(link.idea_id)
        for idea in ideas:
            if idea.id in idea_ids:
                self.criteria_links.append(VotingCriterionWidgetLink(
                    widget=self, idea=idea))

    def add_votable(self, idea):
        if idea not in self.votable_ideas:
            self.votable_idea_links.append(VotableIdeaWidgetLink(
                widget=self, idea=idea))

    def remove_votable(self, idea):
        for link in self.votable_idea_links:
            if link.idea == idea:
                self.votable_idea_links.remove(link)
                return

    def set_votables(self, ideas):
        idea_ids = {idea.id for idea in ideas}
        for link in list(self.votable_idea_links):
            if link.idea_id not in idea_ids:
                self.votable_idea_links.remove(link)
                self.db.delete(link)
            else:
                idea_ids.remove(link.idea_id)
        for idea in ideas:
            if idea.id in idea_ids:
                self.votable_idea_links.append(VotableIdeaWidgetLink(
                    widget=self, idea=idea))

    @classmethod
    def extra_collections(cls):
        class CriterionCollection(RelationCollectionDefinition):
            # The set of voting criterion ideas.
            # Not to be confused with http://www.criterion.com/
            def __init__(self, cls):
                super(CriterionCollection, self).__init__(
                    cls, cls.criteria)

            def decorate_query(self, query, owner_alias, last_alias, parent_instance, ctx):
                widget = owner_alias
                idea = last_alias
                return query.join(idea.has_criterion_links).join(
                    widget).filter(widget.id == parent_instance.id)

        @collection_creation_side_effects.register(
            inst_ctx=Idea, ctx='VotingWidget.criteria')
        def add_criterion_link(inst_ctx, ctx):
            yield InstanceContext(
                inst_ctx['has_criterion_links'],
                VotingCriterionWidgetLink(idea=inst_ctx._instance,
                                          widget=ctx.owner_alias))

        @collection_creation_side_effects.register(
            inst_ctx=AbstractIdeaVote, ctx='VotingWidget.criteria')
        def add_criterion_relation(inst_ctx, ctx):
            criterion_ctx = ctx.find_collection(
                'VotingWidget.criteria')
            # find instance context above me
            search_ctx = ctx
            while (search_ctx.__parent__ and
                   search_ctx.__parent__ != criterion_ctx):
                search_ctx = search_ctx.__parent__
            assert search_ctx.__parent__
            inst_ctx._instance.criterion = search_ctx._instance

        class VotableCollection(RelationCollectionDefinition):
            # The set of votable ideas.
            def __init__(self, cls):
                super(VotableCollection, self).__init__(
                    cls, cls.votable_ideas, "targets")

            def decorate_query(self, query, owner_alias, last_alias, parent_instance, ctx):
                widget = owner_alias
                idea = last_alias
                query = query.join(idea.has_votable_links).join(
                    widget).filter(widget.id == parent_instance.id)
                return query

        @collection_creation_side_effects.register(
            inst_ctx=Idea, ctx='VotingWidget.targets')
        def add_votable_link(inst_ctx, ctx):
            yield InstanceContext(
                inst_ctx['has_votable_links'],
                VotableIdeaWidgetLink(
                    idea=inst_ctx._instance,
                    widget=ctx.parent_instance))

        return (CriterionCollection(cls),
                VotableCollection(cls))

    # @property
    # def criteria(self):
    #     return [cl.idea for cl in self.criteria_links]

class MultiCriterionVotingWidget(VotingWidget):
    __mapper_args__ = {
        'polymorphic_identity': 'multicriterion_voting_widget',
    }

class TokenVotingWidget(VotingWidget):
    __mapper_args__ = {
        'polymorphic_identity': 'token_voting_widget',
    }


class WidgetUserConfig(DiscussionBoundBase):
    __tablename__ = "widget_user_config"

    id = Column(Integer, primary_key=True)

    widget_id = Column(
        Integer,
        ForeignKey('widget.id',
                   ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False, index=True)
    widget = relationship(Widget, backref=backref(
        "user_configs", cascade="all, delete-orphan"))

    user_id = Column(
        Integer,
        ForeignKey('user.id',
                   ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False, index=True)
    user = relationship(User)

    state = Column('settings', Text)  # JSON blob

    @property
    def state_json(self):
        if self.state:
            return json.loads(self.state)
        return {}

    @state_json.setter
    def state_json(self, val):
        self.state = json.dumps(val)

    def get_discussion_id(self):
        widget = self.widget or Widget.get(self.widget_id)
        return widget.get_discussion_id()

    @classmethod
    def get_discussion_conditions(cls, discussion_id, alias_maker=None):
        return ((cls.widget_id == Widget.id),
                (Widget.discussion_id == discussion_id))

    discussion = relationship(
        Discussion, viewonly=True, uselist=False, secondary=Widget.__table__,
        info={'rdf': QuadMapPatternS(None, ASSEMBL.in_conversation)})

    crud_permissions = CrudPermissions(P_ADD_POST)  # all participants...



Idea.has_votable_links = relationship(VotableIdeaWidgetLink)
Idea.has_voted_links = relationship(VotedIdeaWidgetLink)
Idea.has_criterion_links = relationship(VotingCriterionWidgetLink)

VotingWidget.votable_ideas = relationship(
    Idea, viewonly=True, secondary=VotableIdeaWidgetLink.__table__,
    primaryjoin=((VotingWidget.id == VotableIdeaWidgetLink.widget_id)
                 & VotableIdeaWidgetLink.polymorphic_filter()),
    secondaryjoin=VotableIdeaWidgetLink.idea_id == Idea.id,
    backref='votable_by_widget')

VotingWidget.voted_ideas = relationship(
    Idea, viewonly=True, secondary=VotedIdeaWidgetLink.__table__,
    primaryjoin=((VotingWidget.id == VotedIdeaWidgetLink.widget_id)
                 & VotedIdeaWidgetLink.polymorphic_filter()),
    secondaryjoin=VotedIdeaWidgetLink.idea_id == Idea.id,
    backref="voted_by_widget")

VotingWidget.criteria = relationship(
    Idea,
    viewonly=True, secondary=VotingCriterionWidgetLink.__table__,
    primaryjoin=((VotingWidget.id == VotingCriterionWidgetLink.widget_id)
                 & VotingCriterionWidgetLink.polymorphic_filter()),
    secondaryjoin=VotingCriterionWidgetLink.idea_id == Idea.id,
    backref='criterion_of_widget')
