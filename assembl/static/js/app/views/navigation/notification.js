/**
 * 
 * @module app.views.navigation.notification
 */

import Marionette from 'marionette.js';

var sidebarNotification = Marionette.View.extend({
  constructor: function sidebarNotification() {
    Marionette.View.apply(this, arguments);
  },

  template: '#tmpl-sidebar-notification'
});

export default sidebarNotification;
