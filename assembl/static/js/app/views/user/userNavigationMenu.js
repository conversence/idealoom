/**
 * 
 * @module app.views.user.userNavigationMenu
 */

var Marionette = require('backbone.marionette');

var $ = require('jquery');
var i18n = require('../../utils/i18n.js');
var Ctx = require('../../common/context.js');
var CollectionManager = require('../../common/collectionManager.js');
var Roles = require('../../utils/roles.js');
var LoaderView = require('../loaderView.js');
var Permissions = require('../../utils/permissions.js');

var userNavigationMenu = LoaderView.extend({
  constructor: function userNavigationMenu() {
    LoaderView.apply(this, arguments);
  },

  template: '#tmpl-userNavigationMenu',
  tagName: 'nav',
  className: 'sidebar-nav',
  selectedSection: undefined,

  initialize: function(options) {
    var that = this;
    var collectionManager = new CollectionManager();
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
