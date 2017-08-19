'use strict';
/**
 * 
 * @module app.views.user.userNavigationMenu
 */

var Marionette = require('backbone.marionette'),
    $ = require('jquery'),
    i18n = require('../../utils/i18n.js'),
    Ctx = require('../../common/context.js'),
    CollectionManager = require('../../common/collectionManager.js'),
    Roles = require('../../utils/roles.js'),
    LoaderView = require('../loaderView.js'),
    Permissions = require('../../utils/permissions.js');

var userNavigationMenu = LoaderView.extend({
  constructor: function userNavigationMenu() {
    LoaderView.apply(this, arguments);
  },

  template: '#tmpl-userNavigationMenu',
  tagName: 'nav',
  className: 'sidebar-nav',
  selectedSection: undefined,

  initialize: function(options) {
    var that = this,
        collectionManager = new CollectionManager();
    this.setLoading(true);

    if ( "selectedSection" in options ){
      this.selectedSection = options.selectedSection;
    }
    collectionManager.getLocalRoleCollectionPromise().then(function(localRoles) {
      if(!that.isDestroyed()) {
        that.localRoles = localRoles;
        that.setLoading(false);
        that.render();
      }
    });
  },

  serializeData: function() {
    if(this.isLoading()) {
      return {};
    }
    return {
      selectedSection: this.selectedSection,
      currentUser: Ctx.getCurrentUser(),
      Permissions: Permissions,
      Roles: Roles,
      localRoles: this.localRoles
    };
  },
});

module.exports = userNavigationMenu;
