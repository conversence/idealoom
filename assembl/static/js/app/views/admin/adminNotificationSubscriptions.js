/**
 * 
 * @module app.views.admin.adminNotificationSubscriptions
 */

import Marionette from 'backbone.marionette';

import CollectionManager from '../../common/collectionManager.js';
import Permissions from '../../utils/permissions.js';
import Ctx from '../../common/context.js';
import i18n from '../../utils/i18n.js';
import $ from 'jquery';
import Promise from 'bluebird';
import AdminNavigationMenu from './adminNavigationMenu.js';

class NotificationView extends Marionette.View.extend({
  template: '#tmpl-adminNotification',
  className: 'controls',

  ui: {
    subscribeCheckbox: ".js_adminNotification"
  },

  events: {
    'click @ui.subscribeCheckbox': 'discussionNotification'
  }
}) {
  serializeData() {
    return {
      i18n: i18n,
      notification: this.model
    }
  }

  discussionNotification(e) {
    var elm = $(e.target);
    var status = elm.is(':checked') ? 'ACTIVE' : 'UNSUBSCRIBED';

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
}

class NotificationListBody extends Marionette.CollectionView.extend({
  childView: NotificationView,
  className: 'mtl'
}) {}

class NotificationList extends Marionette.View.extend({
  template: '#tmpl-adminNotificationList',

  regions: {
    list: '.control-group',
  }
}) {
  onRender() {
    this.showChildView('list', new NotificationListBody({
      collection: this.collection,
    }));
  }
}

class defaultNotification extends Marionette.View.extend({
  template: '#tmpl-defaultNotification',

  ui: {
    autoSubscribeCheckbox: ".js_adminAutoSubscribe"
  },

  events: {
    'click @ui.autoSubscribeCheckbox': 'updateAutoSubscribe'
  }
}) {
  updateAutoSubscribe() {
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
}

class adminNotificationSubscriptions extends Marionette.View.extend({
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
  }
}) {
  initialize() {

    if (!Ctx.getCurrentUser().can(Permissions.ADMIN_DISCUSSION)) {
      // TODO ghourlier: Éviter que les gens n'ayant pas l'autorisation accèdent à cet écran.
      alert("This is an administration screen.");
      return;
    }
  }

  onRender() {
    var that = this;
    var collectionManager = new CollectionManager();

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
  }

  close() {
    this.$('.bx-alert-success').addClass('hidden');
  }
}

export default adminNotificationSubscriptions;
