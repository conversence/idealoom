"""The SQLAlchemy_ models of IdeaLoom.

The base class of all models is Base, derived from :py:class:`assembl.lib.sqla.BaseOps`.
Here, we also define some other base-level classes, such as :py:class:`DiscussionBoundBase` and :py:class:`DiscussionBoundTombstone`.

.. figure:: ../er_diagram.svg
    :width: 100%
    :target: ../_images/er_diagram.svg

    Entity-relation diagram

.. _SQLAlchemy: http://www.sqlalchemy.org/
"""

from builtins import object
from abc import abstractmethod, ABCMeta

from sqlalchemy import and_
from sqlalchemy.ext.declarative import DeclarativeMeta
from future.utils import with_metaclass

from ..lib.abc import abstractclassmethod
from ..lib.sqla import (
    Base, get_metadata, get_session_maker, PrivateObjectMixin,
    get_named_object, get_database_id, Tombstone, CrudOperation,
    TimestampedMixin)
from ..lib.history_mixin import (
    TombstonableMixin, HistoryMixin, OriginMixin, HistoryMixinWithOrigin,
    TombstonableOriginMixin, reln_in_history, as_time_proxy)


Base.reln_in_history = reln_in_history
Base.as_time_proxy = as_time_proxy


class DeclarativeAbstractMeta(DeclarativeMeta, ABCMeta):
    "Allows to declare abstract SQLAlchemy classes"
    pass


class AbstractBase(with_metaclass(DeclarativeAbstractMeta, Base)):
    __abstract__ = True


class DiscussionBoundBase(AbstractBase):
    """Base class for models that are bound to a specific discussion.

    These models will deleted if the discussion is deleted.
    They need to have a relationship to the discussion, but this relationship
    need not be direct. Subclasses need to define :py:meth:`get_discussion_id`
    and :py:meth:`get_discussion_conditions`.
    """
    __abstract__ = True
    __external_typename = None

    @abstractmethod
    def get_discussion_id(self):
        "Get the ID of an associated discussion object, if any."
        return self.discussion_id or self.discussion.id

    def get_discussion(self):
        from .discussion import Discussion
        return Discussion.get(self.get_discussion_id())

    def local_permissions(self, user_id, discussion=None, include_global=False):
        return super(DiscussionBoundBase, self).local_permissions(
            user_id, discussion or self.get_discussion(), include_global)

    def send_to_changes(self, connection=None, operation=CrudOperation.UPDATE,
                        discussion_id=None, view_def="changes"):
        if not connection:
            # WARNING: invalidate has to be called within an active transaction.
            # This should be the case in general, no need to add a transaction manager.
            connection = self.db.connection()
        if 'cdict' not in connection.info:
            connection.info['cdict'] = {}
        connection.info['cdict'][(self.uri(), view_def)] = (
            discussion_id or self.get_discussion_id(), self)

    @abstractclassmethod
    def get_discussion_conditions(cls, discussion_id, alias_maker=None):
        "Returns a list of SQLA expressions that constrain a query on this class to a given discussion."
        return (cls.discussion_id == discussion_id, )

    def unique_query(self):
        query, usable = super(DiscussionBoundBase, self).unique_query()
        discussion_id = self.get_discussion_id()
        if discussion_id:
            query = query.filter(and_(*self.get_discussion_conditions(discussion_id)))
        return (query, usable)

    def tombstone(self):
        return DiscussionBoundTombstone(self)

    def get_default_parent_context(self, request=None, user_id=None):
        for r in self.__class__.__mapper__.relationships:
            if r.mapper.class_ == Discussion and r.back_populates:
                discussion = getattr(self, r.key)
                return discussion.get_collection_context(
                    r.back_populates, request=request, user_id=user_id)
        return super(DiscussionBoundBase, self
                     ).get_default_parent_context(request, user_id)

    def container_url(self):
        for r in self.__class__.__mapper__.relationships:
            if r.mapper.class_ == Discussion and r.back_populates:
                return '/data/Discussion/%d/%s' % (
                    self.get_discussion_id(), r.back_populates)

    def _do_update_from_json(
            self, json, parse_def, context,
            duplicate_handling=None, object_importer=None):
        # hard to live without a discussion.
        if self.__class__.__mapper__.relationships.get('discussion', None):
            self.discussion = context.get_instance_of_class(Discussion)
        return super(DiscussionBoundBase, self)._do_update_from_json(
            json, parse_def, context,
            duplicate_handling=duplicate_handling,
            object_importer=object_importer)

    def principals_with_read_permission(self):
        from ..auth import P_READ
        from ..auth.util import roles_with_permission
        from .auth import User
        permissions = self.crud_permissions
        if permissions.read == P_READ:
            return None  # i.e. everyone
        # TODO: CACHE!!!
        base = roles_with_permission(self.get_discussion(), permissions.read)
        # make this into a protocol!
        creator_id = getattr(self, 'creator_id', None)
        if creator_id:
            base.append(User.uri_generic(creator_id))
        return base


class DiscussionBoundTombstone(Tombstone):
    "A :py:class:`assembl.lib.sqla.Tombstone` that is bound to a discussion"
    def __init__(self, ob, **kwargs):
        super(DiscussionBoundTombstone, self).__init__(ob, **kwargs)
        self.discussion_id = ob.get_discussion_id()

    def send_to_changes(self, connection, operation=CrudOperation.DELETE,
                        discussion_id=None, view_def="changes"):
        assert connection
        if 'cdict' not in connection.info:
            connection.info['cdict'] = {}
        connection.info['cdict'][(self.uri, view_def)] = (
            discussion_id or self.discussion_id, self)


class NamedClassMixin(object):
    """A mix-in for models that have a globally unique name"""

    @abstractclassmethod
    def get_naming_column_name(self):
        return "name"

    @classmethod
    def getByName(cls, name, session=None, query=None, parent_object=None):
        session = session or cls.default_db
        query = query or session.query(cls)
        return query.filter_by(**{cls.get_naming_column_name(): name}).first()

    @classmethod
    def get_instance(cls, id, session=None):
        instance = super(NamedClassMixin, cls).get_instance(id, session)
        if instance:
            return instance
        return cls.getByName(id, session)


class ContextualNamedClassMixin(NamedClassMixin):
    """A mix-in for models that have a unique name within a context"""

    @abstractclassmethod
    def get_parent_relation_name(self):
        return "name"

    @classmethod
    def getByName(cls, name, session=None, query=None, parent_object=None):
        assert parent_object, "parent object must be given"
        session = session or cls.default_db
        query = query or session.query(cls)
        query = query.filter_by(**{cls.get_parent_relation_name(): parent_object})
        return super(ContextualNamedClassMixin, cls).getByName(
            name, session, query, parent_object)

    @classmethod
    def get_instance(cls, id, session=None):
        # bypass NamedClassMixin.get_instance
        return super(NamedClassMixin, cls).get_instance(id, session)


from .uriref import (
    URIRefDb,
)
from .import_records import (
    ImportRecord,
)
from .auth import (
    AbstractAgentAccount,
    AgentProfile,
    AgentStatusInDiscussion,
    AnonymousUser,
    EmailAccount,
    IdentityProvider,
    LanguagePreferenceCollection,
    PartnerOrganization,
    User,
    UserLanguagePreference,
)
from .social_auth import (
    Nonce,
    Association,
    Code,
    SocialAuthAccount,
)
from .langstrings import (
    LocaleLabel,
    LangString,
    LangStringEntry,
)
from .publication_states import (
    PublicationFlow,
    PublicationState,
    PublicationTransition,
    StateDiscussionPermission,
)
from .permissions import (
    DiscussionPermission,
    LocalUserRole,
    Permission,
    Role,
    UserRole,
    UserTemplate,
)
from .discussion import Discussion
from .user_key_values import (
    # AbstractNamespacedKeyValue,
    # AbstractPerUserNamespacedKeyValue,
    DiscussionPerUserNamespacedKeyValue,
    IdeaNamespacedKeyValue,
    # NamespacedUserKVCollection,
    # UserNsDict,
    UserPreferenceCollection,
)
from .preferences import Preferences
from .generic import (
    AnnotatorSource,
    Content,
    ContentSource,
    ContentSourceIDs,
    PostSource,
)
from .post import (
    LocalPost,
    IdeaProposalPost,
    ImportedPost,
    Post,
    PublicationStates,
    WidgetPost,
    SynthesisPost,
)
from .mail import (
    AbstractFilesystemMailbox,
    AbstractMailbox,
    Email,
    IMAPMailbox,
    MaildirMailbox,
    MailingList,
)
from .idea import (
    Idea,
    IdeaLink,
    RootIdea,
    IdeaLocalUserRole,
)
from .action import (
    Action,
    ActionOnIdea,
    ActionOnPost,
    CollapsePost,
    ExpandPost,
    LikedPost,
    UniqueActionOnIdea,
    UniqueActionOnPost,
    ViewIdea,
    ViewPost,
)
from .idea_content_link import (
    Extract,
    IdeaContentLink,
    IdeaContentNegativeLink,
    IdeaContentPositiveLink,
    IdeaContentWidgetLink,
    IdeaRelatedPostLink,
    IdeaThreadContextBreakLink,
    AnnotationSelector,
    TextFragmentIdentifier,
)
from .idea_graph_view import (
    ExplicitSubGraphView,
    IdeaGraphView,
    SubGraphIdeaAssociation,
    SubGraphIdeaLinkAssociation,
    Synthesis,
    TableOfContents,
)
from .votes import (
    AbstractIdeaVote,
    AbstractVoteSpecification,
    BinaryIdeaVote,
    BinaryVoteSpecification,
    LickertIdeaVote,
    LickertVoteSpecification,
    MultipleChoiceIdeaVote,
    MultipleChoiceVoteSpecification,
    TokenCategorySpecification,
    TokenIdeaVote,
    TokenVoteSpecification,
)
from .annotation import (
    Webpage,
)
from .timeline import (
    DiscussionMilestone,
    DiscussionPhase,
    DiscussionSession,
    TimelineEvent,
)
from .widgets import (
    BaseIdeaWidget,
    BaseIdeaWidgetLink,
    CreativitySessionWidget,
    GeneratedIdeaWidgetLink,
    IdeaCreatingWidget,
    IdeaCreativitySessionWidgetLink,
    IdeaDescendantsShowingWidgetLink,
    IdeaInspireMeWidgetLink,
    IdeaShowingWidgetLink,
    IdeaWidgetLink,
    InspirationWidget,
    MultiCriterionVotingWidget,
    TokenVotingWidget,
    VotableIdeaWidgetLink,
    VotedIdeaWidgetLink,
    VotingCriterionWidgetLink,
    VotingWidget,
    Widget,
    WidgetUserConfig,
)

from .notification import (
    NotificationSubscription,
    NotificationSubscriptionGlobal,
    NotificationSubscriptionOnPost,
    NotificationSubscriptionOnIdea,
    NotificationSubscriptionOnExtract,
    NotificationSubscriptionOnUserAccount,
    NotificationSubscriptionFollowSyntheses,
    NotificationSubscriptionFollowAllMessages,
    NotificationSubscriptionFollowOwnMessageDirectReplies,
    NotificationSubscriptionStatus,
    Notification,
    NotificationCreationOrigin,
    NotificationDeliveryStateType,
    NotificationOnPost,
    NotificationOnPostCreated,
)

from .feed_parsing import (
    FeedPostSource,
    LoomioPostSource,
    FeedPost,
    LoomioFeedPost,
    WebLinkAccount,
    LoomioAccount,
)
from .edgesense_drupal import (
    EdgeSenseDrupalSource,
    SourceSpecificAccount,
    SourceSpecificPost,
)
from .facebook_integration import (
    FacebookAccessToken,
    FacebookGenericSource,
    FacebookGroupSource,
    FacebookPagePostsSource,
    FacebookPageFeedSource,
    FacebookSinglePostSource,
    FacebookPost
)

from .attachment import (
    Document,
    File,
    Attachment,
    PostAttachment,
    IdeaAttachment
)

from .announcement import (
    Announcement,
    IdeaAnnouncement,
)
from .import_record_source import (
    ImportRecordSource,
)
from .idea_source import (
    CatalystIdeaSource,
    IdeaSource,
    IdeaLoomIdeaSource,
)
from .hypothesis_source import (
    HypothesisExtractSource,
)


def includeme(config):
    config.include('.import_records')
    config.include('.preferences')
