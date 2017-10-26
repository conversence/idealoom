/**
 * 
 * @module app.views.admin.sourceEditViews
 */
import Marionette from 'backbone.marionette';

import i18n from '../../utils/i18n.js';
import CollectionManager from '../../common/collectionManager.js';
import Promise from 'bluebird';
import SourceViewBase from '../sourceEditView.js';

//This needs to become the emailSourceEditView

var EmailSourceEditView = SourceViewBase.extend({
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
  }

});

export default {
  EmailSource: EmailSourceEditView
};
