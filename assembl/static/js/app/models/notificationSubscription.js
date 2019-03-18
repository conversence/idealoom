/**
 * A user's subscription to being notified of certain situations
 * @module app.models.notificationSubscription
 */

import Base from './base.js';

import Ctx from '../common/context.js';

/**
 * Notification subscription model
 * Frontend model for :py:class:`assembl.models.notification.NotificationSubscription`
 * @class app.models.notificationSubscription.notificationsSubscriptionModel
 * @extends app.models.base.BaseModel
 */

class notificationsSubscriptionModel extends Base.Model.extend({
  defaults: {
    '@id': null,
    '@type': null,
    status: null,
    followed_object: null,
    parent_subscription: null,
    discussion: null,
    last_status_change_date: null,
    created: null,
    creation_origin: null,
    human_readable_description: null,
    user: null
  }
}) {
  validate(attrs, options) {
    /**
     * check typeof variable
     * */
     
  }
}

/**
 * Notifications subscription collection
 * @class app.models.notificationSubscription.notificationsSubscriptionCollection
 * @extends app.models.base.BaseCollection
 */

class notificationsSubscriptionCollection extends Base.Collection.extend({
  model: notificationsSubscriptionModel
}) {
  /**
   * Set the collection url for a specific user subscription
   */
  setUrlToUserSubscription() {
    var root = 'Discussion/' + Ctx.getDiscussionId() + '/all_users/' + Ctx.getCurrentUserId() + '/notification_subscriptions';
    this.url = Ctx.getApiV2Url(root);
  }

  /**
   * Set the collection url for global discussion template subscription
   */
  setUrlToDiscussionTemplateSubscriptions() {
    this.url = Ctx.getApiV2DiscussionUrl("user_templates/-/notification_subscriptions");
  }
}

export default {
  Model: notificationsSubscriptionModel,
  Collection: notificationsSubscriptionCollection
};
