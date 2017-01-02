'use strict';
/**
 * 
 * @module app.views.admin.adminNotificationSubscriptions
 */

var Marionette = require('backbone.marionette'),
    CollectionManager = require('../../common/collectionManager.js'),
    Permissions = require('../../utils/permissions.js'),
    Ctx = require('../../common/context.js'),
    i18n = require('../../utils/i18n.js'),
    $ = require('jquery'),
    Promise = require('bluebird'),
    AdminNavigationMenu = require('./adminNavigationMenu.js');

var NotificationView = Marionette.View.extend({
  constructor: function NotificationView() {
    Marionette.View.apply(this, arguments);
  },

  template: '#tmpl-adminNotification',
  className: 'controls',
  ui: {
    subscribeCheckbox: ".js_adminNotification"
  },
  events: {
    'click @ui.subscribeCheckbox': 'discussionNotification'
  },
  serializeData: function() {
    return {
      i18n: i18n,
      notification: this.model
    }
  },
  discussionNotification: function(e) {
    var elm = $(e.target),
        status = elm.is(':checked') ? 'ACTIVE' : 'UNSUBSCRIBED';

    this.model.set("status", status);
    this.model.save(null, {
      success: function(model, resp) {
        $('.bx-alert-success').removeClass('hidden');
      },
      error: function(model, resp) {
        console.error('ERROR: discussionNotification', resp);
      }
    });
  }
});

var NotificationListBody = Marionette.CollectionView.extend({
  constructor: function NotificationListBody() {
    Marionette.CollectionView.apply(this, arguments);
  },

  childView: NotificationView,
  className: 'mtl',
});

var NotificationList = Marionette.View.extend({
  constructor: function NotificationList() {
    Marionette.View.apply(this, arguments);
  },

  template: '#tmpl-adminNotificationList',
  regions: {
    list: '.control-group',
  },
  onRender: function() {
    this.showChildView('list', new NotificationListBody({
      collection: this.collection,
    }));
  },
});

var defaultNotification = Marionette.View.extend({
  constructor: function defaultNotification() {
    Marionette.View.apply(this, arguments);
  },

  template: '#tmpl-defaultNotification',
  ui: {
    autoSubscribeCheckbox: ".js_adminAutoSubscribe"
  },
  events: {
    'click @ui.autoSubscribeCheckbox': 'updateAutoSubscribe'
  },

  updateAutoSubscribe: function() {
    var val = (this.$('.autoSubscribe:checked').val()) ? true : false;

    this.model.set('subscribe_to_notifications_on_signup', val);

    this.model.save(null, {
      success: function(model, resp) {

      },
      error: function(model, resp) {
        console.error(model, resp);
      }
    })
  }
});

var adminNotificationSubscriptions = Marionette.View.extend({
  constructor: function adminNotificationSubscriptions() {
    Marionette.View.apply(this, arguments);
  },

  template: '#tmpl-adminNotificationSubscriptions',
  className: 'admin-notifications',
  regions: {
    notification:'#notification-content',
    autoSubscribe:'#notification-auto-subscribe',
    navigationMenuHolder: '.navigation-menu-holder'
  },
  ui: {
    close: '.bx-alert-success .bx-close'
  },
  events: {
    'click @ui.close': 'close'
  },
  initialize: function() {

    if (!Ctx.getCurrentUser().can(Permissions.ADMIN_DISCUSSION)) {
      // TODO ghourlier: Éviter que les gens n'ayant pas l'autorisation accèdent à cet écran.
      alert("This is an administration screen.");
      return;
    }
  },

  onRender: function() {
    var that = this,
        collectionManager = new CollectionManager();

    Promise.join(collectionManager.getDiscussionModelPromise(),
        collectionManager.getNotificationsDiscussionCollectionPromise(),
            function(Discussion, NotificationsDiscussion) {

              var defaultNotif = new defaultNotification({
                model: Discussion
              });
              that.showChildView('autoSubscribe', defaultNotif);

              var notif = new NotificationList({
                collection: NotificationsDiscussion
              });
              that.showChildView('notification', notif);

            });

    var menu = new AdminNavigationMenu.discussionAdminNavigationMenu(
      {selectedSection: "notifications"});
    this.showChildView('navigationMenuHolder', menu);
  },

  close: function() {
    this.$('.bx-alert-success').addClass('hidden');
  }

});

module.exports = adminNotificationSubscriptions;
