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
class SourceViewBase extends LoaderView.extend({
  ui: {
    submit: '.js_saveSource',
  },

  events: {
    'click @ui.submit': 'submitForm'
  }
}) {
  submitForm(e) {
    e.preventDefault();
    this.saveModel();
  }

  /**
   * A function to override by sub-class to get the
   * model changed values
   * @returns Object of values for the model to change
   */
  fetchValues() {
    throw new Error("Cannot call fetchValues on an abstract class!");
  }

  saveModel() {
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
}

class EmailSourceEditView extends SourceViewBase.extend({
  template: '#tmpl-emailSource'
}) {
  fetchValues() {
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
  }
}

class AnnotatorSourceEditView extends SourceViewBase {}


class HypothesisExtractView extends SourceViewBase.extend({
  template: '#tmpl-hypothesisExtractSource'
}) {
  fetchValues() {
    return {
      name: this.$('#name').val(),
      api_key: this.$('#api_key').val(),
      user: this.$('#user').val(),
      group: this.$('#group').val(),
      tag: this.$('#tag').val(),
      document_url: this.$('#document_url').val(),
    }
  }
}


class IdeaSourceEditView extends SourceViewBase.extend({
  template: '#tmpl-IdeaSource'
}) {
  initialize(options) {
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
  }

  serializeData() {
    if (this.isLoading())
      return {};
    return _.extend(this.model.toJSON(), {
      langPrefs: this.langPrefs,
      pubStates: this.pubStates,
    });
  }

  fetchValues() {
    return {
      name: this.$('#name').val(),
      source_uri: this.$('#source_uri').val(),
      data_filter: this.$('#data_filter').val(),
      update_back_imports: this.$('#update_back_imports').prop('checked'),
      target_state_label: this.$('#target_state_label').val(),
    }
  }
}

class IdeaLoomIdeaSourceEditView extends IdeaSourceEditView.extend({
  template: '#tmpl-IdeaLoomIdeaSource'
}) {
  fetchValues() {
    const base = super.fetchValues(...arguments);
    return _.extend(base, {
      username: this.$('#username').val(),
      password: this.$('#password').val(),
    });
  }
}

class FeedPostSourceEditView extends SourceViewBase.extend({
  template: '#tmpl-FeedPostSource'
}) {
  serializeData() {
    return _.extend(this.model.toJSON(), {
      parserClasses: this.model.knownParsers,
    });
  }

  fetchValues() {
    return {
      name: this.$('#name').val(),
      url: this.$('#url').val(),
      parser_full_class_name: this.$('#parser_full_class_name').val(),
    }
  }
}


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
    case Types.HYPOTHESIS_EXTRACT_SOURCE:
      return HypothesisExtractView;
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
