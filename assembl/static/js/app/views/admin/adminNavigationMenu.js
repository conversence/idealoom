/**
 * 
 * @module app.views.admin.adminNavigationMenu
 */

var Marionette = require('backbone.marionette');

var $ = require('jquery');
var i18n = require('../../utils/i18n.js');
var Permissions = require('../../utils/permissions.js');
var Ctx = require('../../common/context.js');

var adminNavigationMenu = Marionette.View.extend({
  constructor: function adminNavigationMenu() {
    Marionette.View.apply(this, arguments);
  },

  tagName: 'nav',
  className: 'sidebar-nav',
  selectedSection: undefined,

  initialize: function(options) {
    if ( "selectedSection" in options ){
      this.selectedSection = options.selectedSection;
    }
  },

  serializeData: function() {
    return {
      selectedSection: this.selectedSection,
      is_sysadmin: Ctx.getCurrentUser().can(Permissions.SYSADMIN),
    };
  },
});

var discussionAdminNavigationMenu = adminNavigationMenu.extend({
  constructor: function discussionAdminNavigationMenu() {
    adminNavigationMenu.apply(this, arguments);
  },
  template:  '#tmpl-discussionAdminNavigationMenu',
});

var globalAdminNavigationMenu = adminNavigationMenu.extend({
  constructor: function globalAdminNavigationMenu() {
    adminNavigationMenu.apply(this, arguments);
  },
  template:  '#tmpl-globalAdminNavigationMenu',
});

module.exports = {
  discussionAdminNavigationMenu: discussionAdminNavigationMenu,
  globalAdminNavigationMenu: globalAdminNavigationMenu,
};
