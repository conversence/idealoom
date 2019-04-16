import _ from 'underscore';

/**
 * 
 * @module app.utils.types
 */

/** 
 * This is the mapping between the actual string values of the backend object
 * types, received in the @type pattribute of the JSON
 */
var Types = {
  DISCUSSION: 'Conversation',
  EXTRACT: 'Excerpt',
  ROOT_IDEA: 'RootIdea',
  IDEA: 'GenericIdeaNode',
  IDEA_LINK: 'DirectedIdeaRelation',
  IDEA_CONTENT_LINK: 'IdeaContentLink',
  IDEA_CONTENT_WIDGET_LINK: 'IdeaContentWidgetLink',
  IDEA_CONTENT_POSITIVE_LINK: 'IdeaContentPositiveLink',
  IDEA_CONTENT_NEGATIVE_LINK: 'IdeaContentNegativeLink',
  IDEA_RELATED_POST_LINK: 'IdeaRelatedPostLink',
  IDEA_THREAD_CONTEXT_BREAK_LINK: 'IdeaThreadContextBreakLink',
  CONTENT: 'SPost',
  POST: 'Post',
  SYNTHESIS_POST: 'SynthesisPost',
  ROLE: 'Role',
  PERMISSION: 'Permission',
  LOCAL_ROLE: 'LocalRole',
  PUB_STATE_PERMISSION: 'StateDiscussionPermission',
  DISCUSSION_PERMISSION: 'DiscussionPermission',
  EMAIL: 'Email',
  SYNTHESIS: 'Synthesis',
  TABLE_OF_CONTENTS: 'TableOfIdeas',
  AGENT_PROFILE: 'Agent',
  USER: 'User',
  PREFERENCES: 'Preferences',
  PARTNER_ORGANIZATION: 'PartnerOrganization',
  TIMELINE_EVENT: 'TimelineEvent',
  DISCUSSION_PHASE: 'DiscussionPhase',
  DISCUSSION_MILESTONE: 'DiscussionMilestone',
  DISCUSSION_SESSION: 'DiscussionSession',
  WEBPAGE: 'Webpage',
  DOCUMENT: 'Document',
  FILE: 'File',
  POST_ATTACHMENT: 'PostAttachment',
  IDEA_ATTACHMENT: 'IdeaAttachment',
  DISCUSSION_ATTACHMENT: 'DiscussionAttachment',
  ANNOUNCEMENT: 'Announcement',
  IDEA_ANNOUNCEMENT: 'IdeaAnnouncement',
  CONTENT_SOURCE: 'Container',
  POST_SOURCE: 'PostSource',
  ABSTRACT_MAILBOX: 'AbstractMailbox',
  IMAPMAILBOX: 'IMAPMailbox',
  MAILING_LIST: 'MailingList',
  ABSTRACT_FILESYSTEM_MAILBOX: 'AbstractFilesystemMailbox',
  MAILDIR_MAILBOX: 'MaildirMailbox',
  FEED_POST_SOURCE: 'FeedPostSource',
  LOOMIO_POST_SOURCE: 'LoomioPostSource',
  HYPOTHESIS_EXTRACT_SOURCE: 'HypothesisExtractSource',
  IDEALOOM_IDEA_SOURCE: 'IdeaLoomIdeaSource',
  CATALYST_IDEA_SOURCE: 'CatalystIdeaSource',
  ANNOTATOR_SOURCE: 'AnnotatorSource',
  EDGE_SENSE_DRUPAL_SOURCE: 'EdgeSenseDrupalSource',
  FACEBOOK_GENERIC_SOURCE: 'FacebookGenericSource',
  FACEBOOK_GROUP_SOURCE: 'FacebookGroupSource',
  FACEBOOK_GROUP_SOURCE_FROM_USER: 'FacebookGroupSourceFromUser',
  FACEBOOK_PAGE_POSTS_SOURCE: 'FacebookPagePostsSource',
  FACEBOOK_PAGE_FEED_SOURCE: 'FacebookPageFeedSource',
  FACEBOOK_SINGLE_POST_SOURCE: 'FacebookSinglePostSource',
  CONTENT_SOURCE_IDS :'ContentSourceIDs',
  LOCALE: "Locale",
  LANGSTRING: "LangString",
  LANGSTRING_ENTRY: "LangStringEntry",
  LANGUAGE_PREFERENCE: "UserLanguagePreference",
  VOTESPECIFICATIONS: "AbstractVoteSpecification",
  TOKENVOTESPECIFICATION: "TokenVoteSpecification",
  WIDGET: "Widget",
  PUBLICATION_FLOW: "PublicationFlow",
  PUBLICATION_STATE: "PublicationState",
  PUBLICATION_TRANSITION: "PublicationTransition",


/*
Utilities for javascript to access python inheritance relationships
*/

  initInheritance: function(inheritance) {
    // This is small, I think it can be synchronous.
    var script = document.getElementById("inheritance-json");
    try {
      this.inheritance = JSON.parse(script.textContent);
    } catch (e) {
      this.inheritance = {};
    }
  },
  getBaseType: function(type) {
    if (this.inheritance === undefined)
        return type;
    while (this.inheritance[type] !== undefined) {
      type = this.inheritance[type][0];
    }

    return type;
  },
  isInstance: function(type, parentType) {
    var that = this;
    if (type == parentType)
      return true;
    if (this.inheritance !== undefined && this.inheritance[type] !== undefined) {
      return _.any(this.inheritance[type], function(t) {
        return that.isInstance(t, parentType);
      });
    }
    return false;
  }
};
Types.initInheritance();

export default Types;

