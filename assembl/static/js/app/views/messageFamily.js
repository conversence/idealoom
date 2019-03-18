/**
 * 
 * @module app.views.messageFamily
 */

import Marionette from 'backbone.marionette';

import _ from 'underscore';
import i18n from '../utils/i18n.js';
import IdeaLoom from '../app.js';
import Ctx from '../common/context.js';
import Types from '../utils/types.js';
import MessageView from './message.js';
import MessageModel from '../models/message.js';
import SynthesisMessageView from './synthesisMessage.js';
import MessageDeletedByUserView from './messageDeletedByUser.js';
import MessageDeletedByAdminView from './messageDeletedByAdmin.js';
import Analytics from '../internal_modules/analytics/dispatcher.js';
import LoaderView from './loaderView.js';
import availableFilters from './postFilters.js';

/**
 * @class app.views.messageFamily.MessageFamilyView
 */
class MessageFamilyView extends LoaderView.extend({
  template: '#tmpl-messageFamily',

  /**
   * @type {string}
   */
  className: 'message-family-container',

  /**
   * Stores the current level
   * @type {number}
   */
  currentLevel: null,

  events: {
      'click >.message-family-arrow>.link-img': 'onIconbuttonClick',

      //'click >.message-family-container>.message-family-arrow>.link-img': 'onIconbuttonClick',
      'click >.message-conversation-block>.js_viewMessageFamilyConversation': 'onViewConversationClick'
    }
}) {
  /**
   * @init
   * @param {MessageModel} obj : the model
   * @param {boolean[]} options.last_sibling_chain : which of the view's ancestors
   *   are the last child of their respective parents.
   */
  initialize(options) {
    this.setLoading(true);
    var that = this;
    if (_.isUndefined(options.last_sibling_chain)) {
      this.last_sibling_chain = [];
    }
    else {
      this.last_sibling_chain = options.last_sibling_chain;
    }

    this.messageListView = options.messageListView;
    if(!options.visitorData) {
      throw new Error("visitorData missing");
    }
    this.visitorData = options.visitorData;
    this.collapsed = options.collapsed;
    this.currentLevel = options.currentLevel;
    this.hasChildren = (_.size(options.hasChildren) > 0);
    this.childViews = options.hasChildren;

    //this.model.on('change:collapsed', this.onCollapsedChange, this);
    //this.listenTo(this.model, 'change:collapsed', this.onCollapsedChange);

    this.level = this.currentLevel !== null ? this.currentLevel : 1;

    if (!_.isUndefined(this.level)) {
      this.currentLevel = this.level;
    }
    this.model.collection.collectionManager.getUserLanguagePreferencesPromise(Ctx).then(function(ulp) {
        that.translationData = ulp.getTranslationData();
        that.setLoading(false);
        that.render();
    });
  }

  serializeData() {
    var hasParentsOrChildrenOutOfScope = false;
    var firstMessage = this.model;
    var numAncestors = undefined;
    var numDescendants = undefined;
    var visitorViewData = this.visitorData.visitorViewData[this.model.id];
    var numAncestorsOutOfContext = 0;
    var numDescendantsOutOfContext = 0;
    var numAuthorsOutOfContext = 0;

    //console.log(this.model.id, visitorViewData);
    if (this.messageListView.isCurrentViewStyleThreadedType()) {
      if ((visitorViewData.filtered_descendant_count !== visitorViewData.real_descendant_count) || visitorViewData.real_ancestor_count !== visitorViewData.level && firstMessage.get("parentId") && this.level === 1) {
        hasParentsOrChildrenOutOfScope = true;
        numAncestorsOutOfContext = visitorViewData.real_ancestor_count - visitorViewData.level;
        numDescendantsOutOfContext = visitorViewData.real_descendant_count - visitorViewData.filtered_descendant_count;
        numAuthorsOutOfContext = visitorViewData.real_descendant_authors_list.length - visitorViewData.filtered_descendant_authors_list.length + visitorViewData.real_ancestor_authors_list.length - visitorViewData.filtered_ancestor_authors_list.length;
      }
    }
    else {
      if (visitorViewData.real_descendant_count > 0 || visitorViewData.real_ancestor_count > 0) {
        hasParentsOrChildrenOutOfScope = true;
        numAncestorsOutOfContext = visitorViewData.real_ancestor_count;
        numDescendantsOutOfContext = visitorViewData.real_descendant_count;
        numAuthorsOutOfContext = _.union(visitorViewData.real_descendant_authors_list, visitorViewData.real_ancestor_authors_list, [this.model.get('idCreator')]).length - 1;
      }
    }

    return {
      id: this.model.get('@id'),
      level: this.level,
      last_sibling_chain: this.last_sibling_chain,
      hasChildren: this.hasChildren,
      hasParentsOrChildrenOutOfScope: hasParentsOrChildrenOutOfScope,
      numAncestorsOutOfContext: numAncestorsOutOfContext,
      numDescendantsOutOfContext: numDescendantsOutOfContext,
      numAuthorsOutOfContext: numAuthorsOutOfContext,
      ctxMessageCountTooltip: i18n.sprintf(i18n.ngettext(
        "%d more message is available in this message's full context.",
        "%d more messages are available in this message's full context.",
        (numAncestorsOutOfContext + numDescendantsOutOfContext)),
        (numAncestorsOutOfContext + numDescendantsOutOfContext)),
      ctxAuthorCountTooltip: i18n.sprintf(i18n.ngettext(
        "Messages available in this message's full context are from %d more author.",
        "Messages available in this message's full context are from %d more authors.",
        numAuthorsOutOfContext), numAuthorsOutOfContext)
    };
  }

  onDestroy() {
    //Marionette view not used in a region
    if(this._messageView) {
      this._messageView.destroy();
    }

    _.each(this.childViews, function(messageFamily) {
      //MessageFamily is a Marionette view called from a non-marionette context,
      //so we manually call destroy, not remove
      messageFamily.destroy();
    });
  }

  /**
   * The render
   * @param {number} [level] The hierarchy level
   * @returns {MessageView}
   */
  onRender() {
    if (this.isLoading()) {
        return {};
    }

    Ctx.removeCurrentlyDisplayedTooltips(this.$el);

    var messageViewClass = MessageView;
    var messageViewOptions = {
      model: this.model,
      messageListView: this.messageListView,
      messageFamilyView: this
    };
    if (!this.model.isInstance(Types.POST)) {
      console.error("not a post?");
    }

    if (this.model.getBEType() == Types.SYNTHESIS_POST) {
      messageViewClass = SynthesisMessageView;
    }

    var publication_state = this.model.get('publication_state');
    if ( publication_state && publication_state in MessageModel.DeletedPublicationStates ){
      if ( publication_state === MessageModel.PublicationStates.DELETED_BY_USER ){
        messageViewClass = MessageDeletedByUserView;
      }
      else { // else if ( publication_state == MessageModel.PublicationState.DELETED_BY_ADMIN ){
        messageViewClass = MessageDeletedByAdminView;
      }
    }

    this._messageView = new messageViewClass(messageViewOptions);

    this._messageView.guardedRender();
    this.messageListView.renderedMessageViewsCurrent[this.model.id] = this._messageView;

    //data['id'] = data['@id'];
    //data['level'] = level;
    //data['last_sibling_chain'] = this.last_sibling_chain;
    //data['hasChildren'] = this.hasChildren;

    if (this.level > 1) {
      if (this.last_sibling_chain[this.level - 1]) {
        this.$el.addClass('last-child');
      } else {
        this.$el.addClass('child');
      }
    } else {
      this.$el.addClass('bx root');
    }

    this.el.setAttribute('data-message-level',  this.level);

    Ctx.initTooltips(this.$el);
    this.$el.find('>.message-family-arrow>.message').replaceWith(this._messageView.el);

    var child_el = this.$('.messagelist-children');
    _.each(this.childViews, function(view) {
      child_el.append(view.el);
    })

    this.onCollapsedChange();

  }

  /**
   * @event
   * Collapse icon has been toggled
   */
  onIconbuttonClick(ev) {
    //var collapsed = this.model.get('collapsed');
    //this.model.set('collapsed', !collapsed);

    this.collapsed = !this.collapsed;

    this.onCollapsedChange();
  }

  /**
   * @event
   * View the entire conversation of a family (possibly composed of a single message)
   */
  onViewConversationClick(ev) {
    var analytics = Analytics.getInstance();
    ev.preventDefault();
    analytics.trackEvent(analytics.events.THREAD_VIEW_COMPLETE_CONVERSATION);

    var filters =  [{filterDef: availableFilters.POST_IS_DESCENDENT_OR_ANCESTOR_OF_POST, value: this.model.id}];
    var ModalGroup = require('./groups/modalGroup.js').default;
    var subject = this.model.get('subject');

    var modal_title = i18n.sprintf(i18n.gettext("Zooming on the conversation around \"%s\""),
                               subject ? subject.bestValue(this.translationData) : '');

    var modalFactory = ModalGroup.filteredMessagePanelFactory(modal_title, filters);
    var modal = modalFactory.modal;
    var messageList = modalFactory.messageList;

    IdeaLoom.rootView.showChildView('slider', modal);
    messageList.showMessageById(this.model.id, undefined, true, true);
  }

  /**
   * @event
   */
  onCollapsedChange() {
    if (this.isLoading()) {
        return;
    }
    var collapsed = this.collapsed;
    var target = this.$el;
    var children = target.find(">.messagelist-children").last();
    if (collapsed) {
      this.$el.removeClass('message--expanded');
      children.hide();
    } else {
      this.$el.addClass('message--expanded');
      children.show();
    }
  }
}

export default MessageFamilyView;
