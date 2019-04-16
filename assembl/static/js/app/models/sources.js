/**
 * An external source of imported messages
 * @module app.models.sources
 */

import Base from './base.js';

import i18n from '../utils/i18n.js';
import Ctx from '../common/context.js';
import Types from '../utils/types.js';
import $ from 'jquery';

/**
 * Source model
 * Frontend model for :py:class:`assembl.models.generic.ContentSource` and :py:class:`assembl.models.post.PostSource`
 * @class app.models.sources.Source
 * @extends app.models.base.BaseModel
 */

class Source extends Base.Model.extend({
  urlRoot: Ctx.getApiV2DiscussionUrl('sources'),
  localizedName: i18n.gettext("Abstract content source"),

  defaults: {
    'created': null,
    /*
      'discussion_id': null,
      If urlRoot of an object is a ClassInstance, then the front-end model
      MUST pass the discussion_id explicitly. However, since the urlRoot
      is an InstanceContext or CollectionContext after Discussion 
      (eg. /data/Conversation/1/sources/ instead of /data/Container),
      the api v2 can infer the discussion_id through the context of the
      traversal. POSTing with discussion_id: null yields a 400 Error from
      backend.
     */
    'last_import': null,
    'connection_error': null,
    'error_description': null,
    'error_backoff_until': null,
    'number_of_imported_posts': 0,
    '@type': Types.CONTENT_SOURCE,
    'is_content_sink': false // Used by API V2 as flag for side-effectful POST creation only.
    // DO NOT use for any other scenario than creating facebook content_sinks
  }
}) {
  fetchUrl() {
    return this.url() + '/fetch_posts';
  }

  doReimport() {
    return $.ajax(
      this.fetchUrl(), {
        method: 'POST',
        contentType: 'application/json',
        dataType: 'json',
        data: {reimport: true}
    });
  }

  doReprocess() {
    return $.ajax(
      this.fetchUrl(), {
        method: 'POST',
        contentType: 'application/json',
        dataType: 'json',
        data: {reprocess: true}
    });
  }
}

class IMAPMailboxSource extends Source.extend({
  localizedName: i18n.gettext("IMAP mailbox")
}) {
  defaults() {
    return _.extend(Source.prototype.defaults, {
      '@type': Types.IMAPMAILBOX,
      'admin_sender': '',
      'post_email_address': '',
      'host': '',
      'folder': '',
      'use_ssl': false,
      'port': 0
    });
  }
}

class MailingListSource extends IMAPMailboxSource.extend({
  localizedName: i18n.gettext("Mailing list")
}) {
  defaults() {
    return _.extend(IMAPMailboxSource.prototype.defaults(), {
      '@type': Types.MAILING_LIST
    });
  }
}

class FacebookSource extends Source {
  //An Abstract Class. Use children only!
  defaults() {
    return _.extend(Source.prototype.defaults, {
      'fb_source_id': null,
      'url_path': null,
      'lower_bound': null,
      'upper_bound': null,
      'creator_id': Ctx.getCurrentUserId()
    });
  }
}

class FacebookSinglePostSource extends FacebookSource.extend({
  localizedName: i18n.gettext("Comments to a given facebook post (by URL)")
}) {
  defaults() {
    return _.extend(FacebookSource.prototype.defaults(), {
      '@type': Types.FACEBOOK_SINGLE_POST_SOURCE
    });
  }
}

class FacebookGroupSource extends FacebookSource.extend({
  localizedName: i18n.gettext("Posts from a Facebook group (by URL)")
}) {
  defaults() {
    return _.extend(FacebookSource.prototype.defaults(), {
      '@type': Types.FACEBOOK_GROUP_SOURCE
    });
  }
}

class FacebookGroupSourceFromUser extends FacebookSource.extend({
  localizedName: i18n.gettext("Posts from a Facebook group to which you're subscribed")
}) {
  defaults() {
    return _.extend(FacebookSource.prototype.defaults(), {
      '@type': Types.FACEBOOK_GROUP_SOURCE_FROM_USER
    });
  }
}

class FacebookPagePostsSource extends FacebookSource.extend({
  localizedName: i18n.gettext("Posts from a Facebook page to which you're subscribed")
}) {
  defaults() {
    return _.extend(FacebookSource.prototype.defaults(), {
      '@type': Types.FACEBOOK_PAGE_POSTS_SOURCE
    });
  }
}

class FacebookPageFeedSource extends FacebookSource.extend({
  localizedName: i18n.gettext("Posts from users on a Facebook page to which you're subscribed")
}) {
  defaults() {
    return _.extend(FacebookSource.prototype.defaults(), {
      '@type': Types.FACEBOOK_PAGE_FEED_SOURCE
    });
  }
}

class ContentSourceId extends Base.Model.extend({
  urlRoot: Ctx.getApiV2Url(Types.CONTENT_SOURCE_IDS),

  defaults: {
    'source_id': '', //Source.id
    'post_id': '', //message.id
    'message_id_in_source': '' //The ID from where the source came from
  }
}) {}

class FeedPostSource extends Source.extend({
  localizedName: i18n.gettext("RSS/Atom post feed"),

  knownParsers: [
    'assembl.models.feed_parsing.PaginatedParsedData',
    'assembl.models.feed_parsing.ParsedData',
  ]
}) {
  defaults() {
    return _.extend(Source.prototype.defaults, {
      '@type': Types.FEED_POST_SOURCE,
      "url": '',
      "parser_full_class_name": 'assembl.models.feed_parsing.PaginatedParsedData',
    });
  }
}

class LoomioPostSource extends FeedPostSource.extend({
  localizedName: i18n.gettext("Loomio post feed")
}) {
  defaults() {
    return _.extend(FeedPostSource.prototype.defaults(), {
      '@type': Types.LOOMIO_POST_SOURCE,
    });
  }
}

class AnnotatorSource extends Source.extend({
  localizedName: i18n.gettext("Annotator extract source")
}) {
  defaults() {
    return _.extend(Source.prototype.defaults, {
      '@type': Types.ANNOTATOR_SOURCE,
    });
  }
}


class ImportRecordSource extends Source {
  defaults() {
    return _.extend(Source.prototype.defaults, {
      "source_uri": '',
      "data_filter": '',
      "update_back_imports": false,
    });
  }
}

class HypothesisExtractSource extends ImportRecordSource.extend({
  localizedName: i18n.gettext("Hypothesis extract source")
}) {
  defaults() {
    return _.extend(ImportRecordSource.prototype.defaults, {
      '@type': Types.HYPOTHESIS_EXTRACT_SOURCE,
      "api_key": null,
      "user": null,
      "group": null,
      "tag": null,
      "document_url": null
    });
  }
}

class IdeaSource extends ImportRecordSource {
  defaults() {
    return _.extend(ImportRecordSource.prototype.defaults, {
      "target_state_label": '',
    });
  }
}

class IdeaLoomIdeaSource extends IdeaSource.extend({
  localizedName: i18n.gettext("IdeaLoom idea source")
}) {
  defaults() {
    return _.extend(IdeaSource.prototype.defaults(), {
      '@type': Types.IDEALOOM_IDEA_SOURCE,
      'username': '',
      'password': '',
    });
  }
}

class CatalystIdeaSource extends IdeaSource.extend({
  localizedName: i18n.gettext("Catalyst Interchange Format idea source")
}) {
  defaults() {
    return _.extend(IdeaSource.prototype.defaults(), {
      '@type': Types.CATALYST_IDEA_SOURCE,
    });
  }
}



function getSourceClassByType(type) {
    switch (type) {
      case Types.FACEBOOK_GENERIC_SOURCE:
        return FacebookGenericSource;
      case Types.FACEBOOK_GROUP_SOURCE:
        return FacebookGroupSource;
      case Types.FACEBOOK_GROUP_SOURCE_FROM_USER:
        return FacebookGroupSourceFromUser;
      case Types.FACEBOOK_PAGE_POSTS_SOURCE:
        return FacebookPagePostsSource;
      case Types.FACEBOOK_PAGE_FEED_SOURCE:
        return FacebookPageFeedSource;
      case Types.FACEBOOK_SINGLE_POST_SOURCE:
        return FacebookSinglePostSource;
      case Types.IMAPMAILBOX:
        return IMAPMailboxSource;
      case Types.MAILING_LIST:
        return MailingListSource;
      case Types.ANNOTATOR_SOURCE:
        return AnnotatorSource;
      case Types.HYPOTHESIS_EXTRACT_SOURCE:
        return HypothesisExtractSource;
      case Types.FEED_POST_SOURCE:
        return FeedPostSource;
      case Types.LOOMIO_POST_SOURCE:
        return LoomioPostSource;
      case Types.IDEALOOM_IDEA_SOURCE:
        return IdeaLoomIdeaSource;
      case Types.CATALYST_IDEA_SOURCE:
        return CatalystIdeaSource;
      default:
        console.error("Unknown source type:" + type);
        return Source;
    }
  }

class sourceCollection extends Base.Collection.extend({
  url: Ctx.getApiV2DiscussionUrl() + 'sources'
}) {
  model(attrs, options) {
    var sourceClass = getSourceClassByType(attrs["@type"]);
    if (sourceClass !== undefined) {
      return new sourceClass(attrs, options);
    }
  }
}

export default {
  Model: {
    Source: Source,
    IMAPMailboxSource,
    MailingListSource,
    FacebookSinglePostSource,
    FacebookGroupSource,
    FacebookGroupSourceFromUser,
    FacebookPagePostsSource,
    FacebookPageFeedSource,
    ContentSourceID: ContentSourceId,
    HypothesisExtractSource,
  },
  Collection: sourceCollection,
  getSourceClassByType: getSourceClassByType
};

