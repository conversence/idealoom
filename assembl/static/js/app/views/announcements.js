/**
 * 
 * @module app.views.announcements
 */

import Marionette from 'backbone.marionette';

import _ from 'underscore';
import $ from 'jquery';
import Promise from 'bluebird';
import i18n from '../utils/i18n.js';
import IdeaLoom from '../app.js';
import Ctx from '../common/context.js';
import CollectionManager from '../common/collectionManager.js';
import Types from '../utils/types.js';
import Announcement from '../models/announcement.js';
import AgentViews from './agent.js';
import LoaderView from './loaderView.js';
import EditableLSField from './reusableDataFields/editableLSField.js';
import CKEditorLSField from './reusableDataFields/ckeditorLSField.js';
import TrueFalseField from './reusableDataFields/trueFalseField.js';

/** 
 */
var AbstractAnnouncementView = LoaderView.extend({
  constructor: function AbstractAnnouncementView() {
    LoaderView.apply(this, arguments);
  },


  initialize: function(options) {
  },

  events: {

  },

  onRender: function() {
    Ctx.removeCurrentlyDisplayedTooltips(this.$el);
    Ctx.initTooltips(this.$el);
  },

  regions: {
    region_title: ".js_announcement_title_region",
    region_body: ".js_announcement_body_region",
    region_shouldPropagateDown: ".js_announcement_shouldPropagateDown_region"
  },

  modelEvents: {
    'change': 'render'
  }
});


var AnnouncementView = AbstractAnnouncementView.extend({
  constructor: function AnnouncementView() {
    AbstractAnnouncementView.apply(this, arguments);
  },

  template: '#tmpl-announcement',

  className: 'attachment'
});

var AnnouncementMessageView = AbstractAnnouncementView.extend({
  constructor: function AnnouncementMessageView() {
    AbstractAnnouncementView.apply(this, arguments);
  },

  template: '#tmpl-announcementMessage',


  attributes: {
    "class": "announcementMessage bx"
  },

  regions: {
    authorAvatarRegion: ".js_author_avatar_region",
    authorNameRegion: ".js_author_name_region"
  },

  modelEvents: {
    'change':'render'
  },

  serializeData: function() {
    if (this.isLoading()) {
      return {}
    }
    var retval = this.model.toJSON();
    retval.creator = this.creator;
    retval.ctx = Ctx;
    retval.hide_creator = this.hideCreator;
    if (retval.body) {
      retval.body = retval.body.bestValue(this.translationData);
    }
    if (retval.title) {
      retval.title = retval.title.bestValue(this.translationData);
    }
    return retval;
  },

  initialize: function(options) {
    var that = this;
    var collectionManager = new CollectionManager();
    this.setLoading(true);
    this.hideCreator = options.hide_creator;
    this.creator = undefined;
    Promise.join(
      this.model.getCreatorPromise(),
      collectionManager.getUserLanguagePreferencesPromise(Ctx),
      function(creator, ulp) {
        if(!that.isDestroyed()) {
          that.translationData = ulp;
          that.creator = creator;
          that.setLoading(false);
          that.render();
        }
    });
  },

  onRender: function() {
    AbstractAnnouncementView.prototype.onRender.call(this);
    if (!this.hideCreator && !this.isLoading()) {
      this.renderCreator();
    }
  },

  renderCreator: function() {
    var agentAvatarView = new AgentViews.AgentAvatarView({
      model: this.creator,
      avatarSize: 50
    });
    this.showChildView('authorAvatarRegion', agentAvatarView);
    var agentNameView = new AgentViews.AgentNameView({
      model: this.creator
    });
    this.showChildView('authorNameRegion', agentNameView);
  },
});

var AnnouncementEditableView = AbstractAnnouncementView.extend({
  constructor: function AnnouncementEditableView() {
    AbstractAnnouncementView.apply(this, arguments);
  },

  template: '#tmpl-announcementEditable',

  className: 'announcementEditable',

  events:_.extend({}, AbstractAnnouncementView.prototype.events, {
    'click .js_announcement_delete': 'onDeleteButtonClick' //Dynamically rendered, do NOT use @ui
  }),

  initialize: function(options) {
    var that = this;
    var collectionManager = new CollectionManager();
    this.setLoading(true);
    collectionManager.getUserLanguagePreferencesPromise(Ctx).then(function(ulp) {
        if(!that.isDestroyed()) {
          that.translationData = ulp;
          that.setLoading(false);
          that.render();
        }
    });
  },

  onRender: function() {
    if (this.isLoading()) {
      return;
    }
    AbstractAnnouncementView.prototype.onRender.call(this);

    var titleView = new EditableLSField({
      'model': this.model,
      'modelProp': 'title',
      translationData: this.translationData,
      'placeholder': i18n.gettext('Please give a title of this announcement...')
    });
    this.showChildView('region_title', titleView);

    var bodyView = new CKEditorLSField({
      'model': this.model,
      'modelProp': 'body',
      translationData: this.translationData,
      'placeholder': i18n.gettext('Please write the content of this announcement here...')
    });
    this.showChildView('region_body', bodyView);

    var shouldPropagateDownView = new TrueFalseField({
      'model': this.model,
      'modelProp': 'should_propagate_down'
    });
    this.showChildView('region_shouldPropagateDown', shouldPropagateDownView);
    
  },

  onDeleteButtonClick: function(ev) {
    this.model.destroy();
  },
});

var AnnouncementListEmptyEditableView = Marionette.View.extend({
  constructor: function AnnouncementListEmptyEditableView() {
    Marionette.View.apply(this, arguments);
  },

  template: "#tmpl-announcementListEmptyEditable",
  ui: {
    'addAnnouncementButton': '.js_announcementAddButton'
  },
  events: {
    'click @ui.addAnnouncementButton': 'onAddAnnouncementButtonClick',
  },
  initialize: function(options) {
    //console.log(options);
    this.objectAttachedTo = options.objectAttachedTo;
    this.collection = options.collection;
  },
  onAddAnnouncementButtonClick: function(ev) {
    var announcement = new Announcement.Model({
      '@type': Types.IDEA_ANNOUNCEMENT,
      creator: Ctx.getCurrentUser().id,
      last_updated_by: Ctx.getCurrentUser().id,
      idObjectAttachedTo: this.objectAttachedTo.id,
      should_propagate_down: true
      }
    );
    this.collection.add(announcement);
    announcement.save();
  },
});

var AnnouncementEditableCollectionView = Marionette.CollectionView.extend({
  constructor: function AnnouncementEditableCollectionView() {
    Marionette.CollectionView.apply(this, arguments);
  },

  initialize: function(options) {
    this.objectAttachedTo = options.objectAttachedTo;
  },
  childView: AnnouncementEditableView,
  emptyView: AnnouncementListEmptyEditableView,
  childViewOptions:  function(model) {
    return {
      objectAttachedTo: this.objectAttachedTo,
      collection: this.collection
    }
  }
});

export default {
    AnnouncementEditableView: AnnouncementEditableView,
    AnnouncementMessageView: AnnouncementMessageView,
    AnnouncementEditableCollectionView: AnnouncementEditableCollectionView
  };
