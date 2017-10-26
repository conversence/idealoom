/**
 * 
 * @module app.views.admin.adminNavigationMenu
 */

import Marionette from 'backbone.marionette';

import $ from 'jquery';
import i18n from '../../utils/i18n.js';
import Permissions from '../../utils/permissions.js';
import Ctx from '../../common/context.js';

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

export default {
  discussionAdminNavigationMenu: discussionAdminNavigationMenu,
  globalAdminNavigationMenu: globalAdminNavigationMenu,
};
