/**
 *
 * @module app.views.user.userNotificationSubscriptions
 */

import Marionette from "backbone.marionette";

import IdeaLoom from "../../app.js";
import $ from "jquery";
import _ from "underscore";
import Promise from "bluebird";
import CollectionManager from "../../common/collectionManager.js";
import Ctx from "../../common/context.js";
import NotificationSubscription from "../../models/notificationSubscription.js";
import RoleModels from "../../models/roles.js";
import i18n from "../../utils/i18n.js";
import Roles from "../../utils/roles.js";
import Accounts from "../../models/accounts.js";
import UserNavigationMenu from "./userNavigationMenu.js";
import LoaderView from "../loaderView.js";
import Analytics from "../../internal_modules/analytics/dispatcher.js";

/**
 * User notification
 * */
class Notification extends Marionette.View.extend({
    template: "#tmpl-userSubscriptions",
    tagName: "label",
    className: "checkbox dispb",

    ui: {
        currentSubscribeCheckbox: ".js_userNotification",
    },

    events: {
        "click @ui.currentSubscribeCheckbox": "userNotification",
    },
}) {
    initialize(options) {
        this.role = options.role;
        this.roles = options.roles;

        this.listenTo(this.roles, "remove add", function (model) {
            this.role = _.size(this.roles) ? model : undefined;
            this.render();
        });

        if (this.model === "undefined") {
            this.setLoading(true);
        }
    }

    serializeData() {
        return {
            subscription: this.model,
            role: this.role,
            i18n: i18n,
        };
    }

    userNotification(e) {
        var elm = $(e.target);
        var status = elm.is(":checked") ? "ACTIVE" : "UNSUBSCRIBED";

        this.model.set("status", status);
        this.model.set("creation_origin", "USER_REQUESTED");
        this.model.save(null, {
            success: function (model, resp) {},
            error: function (model, resp) {
                console.error("ERROR: userNotification", resp);
            },
        });
    }

    updateRole(role) {
        this.role = role;
        this.render();
    }
}

class Notifications extends Marionette.CollectionView.extend({
    childView: Notification,

    collectionEvents: {
        reset: "render",
    },
}) {
    initialize(options) {
        this.collection = options.notificationsUser;
        this.childViewOptions = {
            role: options.role,
            roles: options.roles,
        };
    }

    updateRole(role) {
        this.childViewOptions.role = role;
        this.children.each(function (child) {
            child.updateRole(role);
        });
    }
}

/**
 * Notification template
 * */
class TemplateSubscription extends Marionette.View.extend({
    template: "#tmpl-templateSubscription",
    tagName: "label",
    className: "checkbox dispb",

    ui: {
        newSubscribeCheckbox: ".js_userNewNotification",
    },

    events: {
        "click @ui.newSubscribeCheckbox": "userNewSubscription",
    },
}) {
    initialize(options) {
        this.role = options.role;
        this.roles = options.roles;
        this.notificationsUser = options.notificationsUser;
        this.notificationTemplates = options.notificationTemplates;

        this.listenTo(this.roles, "remove add", function (model) {
            this.role = _.size(this.roles) ? model : undefined;
            this.render();
        });
    }

    serializeData() {
        return {
            subscription: this.model,
            role: this.role,
            i18n: i18n,
        };
    }

    userNewSubscription(e) {
        var elm = $(e.target);
        var that = this;
        var status = elm.is(":checked") ? "ACTIVE" : "UNSUBSCRIBED";

        // var notificationSubscriptionTemplateModel = this.notificationTemplates.get(elm.attr('id'));
        var notificationSubscriptionTemplateModel = this.notificationTemplates.find(
            function (notif) {
                return notif.id === elm.attr("id");
            }
        );

        var notificationSubscriptionModel = new NotificationSubscription.Model({
            creation_origin: "USER_REQUESTED",
            status: status,
            "@type": notificationSubscriptionTemplateModel.get("@type"),
            discussion: notificationSubscriptionTemplateModel.get("discussion"),
            human_readable_description: notificationSubscriptionTemplateModel.get(
                "human_readable_description"
            ),
        });

        this.notificationsUser.add(notificationSubscriptionModel);

        notificationSubscriptionModel.save(null, {
            success: function (model, response, options) {
                that.notificationTemplates.remove(
                    notificationSubscriptionTemplateModel
                );
            },
            error: function (model, resp) {
                that.notificationsUser.remove(notificationSubscriptionModel);
                console.error("ERROR: userNewSubscription", resp);
            },
        });
    }

    updateRole(role) {
        this.role = role;
        this.render();
    }
}

class TemplateSubscriptions extends Marionette.CollectionView.extend({
    childView: TemplateSubscription,

    collectionEvents: {
        reset: "render",
    },
}) {
    initialize(options) {
        var addableGlobalSubscriptions = new Backbone.Collection();
        this.notificationTemplates = options.notificationTemplates;

        options.notificationTemplates.each(function (template) {
            var alreadyPresent = options.notificationsUser.find(function (
                subscription
            ) {
                if (subscription.get("@type") === template.get("@type")) {
                    return true;
                } else {
                    return false;
                }
            });
            if (alreadyPresent === undefined) {
                addableGlobalSubscriptions.add(template);
            }
        });

        this.collection = addableGlobalSubscriptions;

        this.childViewOptions = {
            role: options.role,
            roles: options.roles,
            notificationsUser: options.notificationsUser,
            notificationTemplates: addableGlobalSubscriptions,
        };
    }

    updateRole(role) {
        this.childViewOptions.role = role;
        this.children.each(function (child) {
            child.updateRole(role);
        });
    }
}

/**
 *  Choose an email to notify user
 * */
class NotificationByEmail extends Marionette.View.extend({
    template: "#tmpl-notificationByEmail",
    tagName: "label",
    className: "radio",

    ui: {
        preferredEmail: ".js_preferred",
    },

    events: {
        "click @ui.preferredEmail": "preferredEmail",
    },
}) {
    serializeData() {
        return {
            account: this.model,
        };
    }

    preferredEmail() {
        var preferred = this.$('input[name="email_account"]:checked').val()
            ? true
            : false;

        this.model.set({ preferred: preferred });

        this.model.save(null, {
            success: function () {
                console.log("success");
            },
            error: function () {
                console.error("error");
            },
        });
    }
}

class NotificationByEmailsList extends Marionette.CollectionView.extend({
    childView: NotificationByEmail,
}) {}

class NotificationByEmails extends Marionette.View.extend({
    template: "#tmpl-notificationByEmails",

    regions: {
        list: ".controls",
    },
}) {
    onRender() {
        this.showChildView(
            "list",
            new NotificationByEmailsList({
                collection: this.collection,
            })
        );
    }
}

/**
 * Subscripbe / Unsubscribe action
 * */
class Subscriber extends Marionette.View.extend({
    template: "#tmpl-userSubscriber",

    ui: {
        unSubscription: ".js_unSubscription",
        subscription: ".js_subscription",
        btnSubscription: ".btnSubscription",
        btnUnsubscription: ".btnUnsubscription",
    },

    events: {
        "click @ui.unSubscription": "unSubscription",
        "click @ui.subscription": "subscription",
    },
}) {
    initialize(options) {
        this.roles = options.roles;
        this.role = options.role;
        this.parent = options.parent;

        var analytics = Analytics.getInstance();
        analytics.changeCurrentPage(analytics.pages.NOTIFICATION_SETTINGS);

        this.listenTo(this.roles, "remove add", function (model) {
            this.role = _.size(this.roles) ? model : undefined;
            this.render();
        });
    }

    serializeData() {
        return {
            role: this.role,
        };
    }

    unSubscription() {
        var that = this;

        if (this.role) {
            this.roles.UnsubscribeUserFromDiscussion();
            this.parent.updateRole(null);
        }
    }

    subscription() {
        var that = this;
        var analytics = Analytics.getInstance();
        analytics.trackEvent(analytics.events.JOIN_DISCUSSION_CLICK);

        if (Ctx.getDiscussionId() && Ctx.getCurrentUserId()) {
            var LocalRolesUser = new RoleModels.localRoleModel({
                role: Roles.PARTICIPANT,
                discussion: "local:Discussion/" + Ctx.getDiscussionId(),
                user_id: Ctx.getCurrentUserId(),
            });

            LocalRolesUser.save(null, {
                success: function (model, resp) {
                    that.roles.add(model);
                    analytics.trackEvent(analytics.events.JOIN_DISCUSSION);
                    that.parent.updateRole(model);
                },
                error: function (model, resp) {
                    console.error("ERROR: joinDiscussion->subscription", resp);
                },
            });
        }
    }
}

class userNotificationSubscriptions extends Marionette.View.extend({
    template: "#tmpl-userNotificationSubscriptions",
    className: "admin-notifications",

    regions: {
        navigationMenuHolder: ".navigation-menu-holder",
        userNotifications: "#userNotifications",
        templateSubscription: "#templateSubscriptions",
        userSubscriber: "#subscriber",
        notifByEmail: "#notifByEmail",
    },
}) {
    onRender() {
        var menu = new UserNavigationMenu({ selectedSection: "notifications" });
        this.showChildView("navigationMenuHolder", menu);

        var that = this;
        var collectionManager = new CollectionManager();

        Promise.join(
            collectionManager.getNotificationsUserCollectionPromise(),
            collectionManager.getNotificationsDiscussionCollectionPromise(),
            collectionManager.getMyLocalRoleCollectionPromise(),
            collectionManager.getConnectedSocketPromise(),
            function (
                NotificationsUser,
                notificationTemplates,
                allRoles,
                socket
            ) {
                that.subscriber = new Subscriber({
                    parent: that,
                    role: allRoles.isUserSubscribedToDiscussion(),
                    roles: allRoles,
                });
                that.showChildView("userSubscriber", that.subscriber);

                that.templateSubscriptions = new TemplateSubscriptions({
                    notificationTemplates: notificationTemplates,
                    notificationsUser: NotificationsUser,
                    role: allRoles.isUserSubscribedToDiscussion(),
                    roles: allRoles,
                });
                that.showChildView(
                    "templateSubscription",
                    that.templateSubscriptions
                );

                that.userNotification = new Notifications({
                    notificationsUser: NotificationsUser,
                    role: allRoles.isUserSubscribedToDiscussion(),
                    roles: allRoles,
                });
                that.showChildView("userNotifications", that.userNotification);
            }
        );

        var emailAccount = new Accounts.Collection();
        var notificationByEmails = new NotificationByEmails({
            collection: emailAccount,
        });
        emailAccount.fetch();

        this.showChildView("notifByEmail", notificationByEmails);
    }

    updateRole(role) {
        var that = this;
        var allRoles = this.userNotification.childViewOptions.roles;
        var notificationTemplates = this.templateSubscriptions
            .notificationTemplates;
        this.userNotification.updateRole(role);
        this.templateSubscriptions.updateRole(role);
        if (this.role == null && role != null) {
            // rebuild the notification collections
            this.getRegion("userNotifications").reset();
            this.getRegion("templateSubscription").reset();
            var collectionManager = new CollectionManager();
            collectionManager
                .getNotificationsUserCollectionPromise(true)
                .then(function (NotificationsUser) {
                    that.userNotification = new Notifications({
                        notificationsUser: NotificationsUser,
                        role: role,
                        roles: allRoles,
                    });
                    that.showChildView(
                        "userNotifications",
                        that.userNotification
                    );

                    that.templateSubscriptions = new TemplateSubscriptions({
                        notificationTemplates: notificationTemplates,
                        notificationsUser: NotificationsUser,
                        role: role,
                        roles: allRoles,
                    });
                    that.showChildView(
                        "templateSubscription",
                        that.templateSubscriptions
                    );
                });
        }
    }

    serializeData() {
        return {
            i18n: i18n,
        };
    }
}

export default userNotificationSubscriptions;
