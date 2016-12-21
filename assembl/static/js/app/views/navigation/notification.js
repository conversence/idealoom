'use strict';
/**
 * 
 * @module app.views.navigation.notification
 */

var Marionette = require('marionette.js');

var sidebarNotification = Marionette.View.extend({
  constructor: function sidebarNotification() {
    Marionette.View.apply(this, arguments);
  },

  template: '#tmpl-sidebar-notification'
});

module.exports = sidebarNotification;
