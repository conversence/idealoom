/**
 * 
 * @module app.views.admin.sourceEditViews
 */
import Marionette from 'backbone.marionette';
import Promise from 'bluebird';
import $ from 'jquery';

import Ctx from '../../common/context.js';
import CollectionManager from '../../common/collectionManager.js';
import Types from '../../utils/types.js';
import Growl from '../../utils/growl.js';
import i18n from '../../utils/i18n.js';
import LoaderView from '../loaderView.js';
import FacebookSourceEditView from '../facebookViews.js';


/**
 * An abstract class that defines the Marionette View
 * to use for the editing of each source in a source list
 * view.
 */
const SourceViewBase = LoaderView.extend({
  constructor: function SourceViewBase() {
    LoaderView.apply(this, arguments);
  },

  ui: {
    submit: '.js_saveSource',
  },

  events: {
    'click @ui.submit': 'submitForm'
  },

  submitForm: function(e) {
    e.preventDefault();
    this.saveModel();
  },

  /**
   * A function to override by sub-class to get the
   * model changed values
   * @returns Object of values for the model to change
   */
  fetchValues: function(){
    throw new Error("Cannot call fetchValues on an abstract class!");
  },

  saveModel: function(){
    var values = this.fetchValues();
    this.model.set(values);
    this.model.save(null, {
      success: function(model, resp){
          Growl.showBottomGrowl(Growl.GrowlReason.SUCCESS, i18n.gettext('Your settings were saved!'));
      },

      error: function(model, resp){
        Growl.showBottomGrowl(Growl.GrowlReason.ERROR, i18n.gettext('Your settings failed to update.'));  
      }
    });
  }
});


const EmailSourceEditView = SourceViewBase.extend({
  constructor: function EmailSourceEditView() {
    SourceViewBase.apply(this, arguments);
  },

  template: '#tmpl-emailSource',

  fetchValues: function(){
    return {
      name: this.$('#name').val(),
      admin_sender: this.$('#admin_sender').val(),
      post_email_address: this.$('#post_email_address').val(),
      host: this.$('#host').val(),
      use_ssl: this.$('#use_ssl:checked').val(),
      folder: this.$('#folder').val(),
      port: parseInt(this.$('#port').val()),
      username: this.$('#username').val(),
      password: this.$('#password').val()
    }
  },
});


const AnnotatorSourceEditView = SourceViewBase.extend({
  constructor: function AnnotatorSourceEditView() {
    SourceViewBase.apply(this, arguments);
  },
});


const IdeaSourceEditView = SourceViewBase.extend({
  template: '#tmpl-IdeaSource',
  constructor: function IdeaSourceEditView() {
    SourceViewBase.apply(this, arguments);
  },
  initialize: function(options) {
    const that = this;
    const collectionManager = new CollectionManager();
    this.setLoading(true);
    Promise.join(
      collectionManager.getUserLanguagePreferencesPromise(Ctx),
      collectionManager.getIdeaPublicationStatesPromise()
    ).then(([langPrefs, pubStates]) => {
      that.langPrefs = langPrefs;
      that.pubStates = pubStates;
      that.setLoading(false);
      that.render();
    });
  },
  serializeData: function() {
    if (this.isLoading())
      return {};
    return _.extend(this.model.toJSON(), {
      langPrefs: this.langPrefs,
      pubStates: this.pubStates,
    });
  },
  fetchValues: function() {
    return {
      name: this.$('#name').val(),
      source_uri: this.$('#source_uri').val(),
      data_filter: this.$('#data_filter').val(),
      target_state_label: this.$('#target_state_label').val(),
    }
  },
});


const IdeaLoomIdeaSourceEditView = IdeaSourceEditView.extend({
  template: '#tmpl-IdeaLoomIdeaSource',
  constructor: function IdeaLoomIdeaSourceEditView() {
    IdeaSourceEditView.apply(this, arguments);
  },
  fetchValues: function() {
    const base = IdeaSourceEditView.prototype.fetchValues.apply(this, arguments);
    return _.extend(base, {
      username: this.$('#username').val(),
      password: this.$('#password').val(),
    });
  },
});

const FeedPostSourceEditView = SourceViewBase.extend({
  template: '#tmpl-FeedPostSource',
  constructor: function FeedPostSourceEditView() {
    SourceViewBase.apply(this, arguments);
  },
  serializeData: function() {
    return _.extend(this.model.toJSON(), {
      parserClasses: this.model.knownParsers,
    });
  },
  fetchValues: function() {
    return {
      name: this.$('#name').val(),
      url: this.$('#url').val(),
      parser_full_class_name: this.$('#parser_full_class_name').val(),
    }
  },
});


function getSourceEditView(model_type) {
  var form;
  switch (model_type) {
    case Types.IMAPMAILBOX:
    case Types.MAILING_LIST:
    case Types.ABSTRACT_FILESYSTEM_MAILBOX:
      return EmailSourceEditView;
    case Types.FACEBOOK_GENERIC_SOURCE:
    case Types.FACEBOOK_GROUP_SOURCE:
    case Types.FACEBOOK_GROUP_SOURCE_FROM_USER:
    case Types.FACEBOOK_PAGE_POSTS_SOURCE:
    case Types.FACEBOOK_PAGE_FEED_SOURCE:
    case Types.FACEBOOK_SINGLE_POST_SOURCE:
      return FacebookSourceEditView.init;
    case Types.ANNOTATOR_SOURCE:
      return AnnotatorSourceEditView;
    case Types.FEED_POST_SOURCE:
    case Types.LOOMIO_POST_SOURCE:
      return FeedPostSourceEditView;
    case Types.CATALYST_IDEA_SOURCE:
      return IdeaSourceEditView;
    case Types.IDEALOOM_IDEA_SOURCE:
      return IdeaLoomIdeaSourceEditView;
    default:
      console.error("Not edit view for source of type "+model_type);
      return;
  }
}


export default getSourceEditView;
