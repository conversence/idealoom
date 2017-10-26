/**
 * 
 * @module app.views.user.profile
 */

var Marionette = require('backbone.marionette');

var $ = require('jquery');
var Agents = require('../../models/agents.js');
var i18n = require('../../utils/i18n.js');
var UserNavigationMenu = require('./userNavigationMenu.js');
var Ctx = require('../../common/context.js');
var Growl = require('../../utils/growl.js');

var profile = Marionette.View.extend({
  constructor: function profile() {
    Marionette.View.apply(this, arguments);
  },

  template: '#tmpl-userProfile',
  className: 'admin-profile',
  ui: {
    close: '.bx-alert-success .bx-close',
    profile: '.js_saveProfile',
    form: '.core-form .form-horizontal'
  },
  regions: {
    navigationMenuHolder: '.navigation-menu-holder'
  },

  initialize: function() {
    this.model = new Agents.Model({'@id': Ctx.getCurrentUserId()});
    this.model.fetch();
  },

  modelEvents: {
    'change sync': 'render'
  },

  events: {
    'click @ui.profile': 'saveProfile',
    'click @ui.close': 'close'
  },

  serializeData: function() {
    return {
      profile: this.model
    }
  },

  onRender: function() {
    // this is in onRender instead of onBeforeRender because of the modelEvents
    var menu = new UserNavigationMenu({selectedSection: "profile"});
    this.showChildView('navigationMenuHolder', menu);
  },

  saveProfile: function(e) {
    e.preventDefault();

    var real_name = this.$('input[name="real_name"]').val();

    this.model.set({ real_name: real_name});

    this.model.save(null, {
      success: function(model, resp) {
        Growl.showBottomGrowl(Growl.GrowlReason.SUCCESS, i18n.gettext('Your settings were saved!'));
      },
      error: function(model, resp) {
        Growl.showBottomGrowl(Growl.GrowlReason.ERROR, i18n.gettext('Your settings failed to update.'));
      }
    })
  },
});

module.exports = profile;
