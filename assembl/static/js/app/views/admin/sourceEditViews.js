/**
 * 
 * @module app.views.admin.sourceEditViews
 */
var Marionette = require('backbone.marionette');

var i18n = require('../../utils/i18n.js');
var CollectionManager = require('../../common/collectionManager.js');
var Promise = require('bluebird');
var SourceViewBase = require('../sourceEditView.js');

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

module.exports = {
  EmailSource: EmailSourceEditView
};
