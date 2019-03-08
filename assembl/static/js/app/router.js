/**
 * The application router.
 * @module app.router
 */

import Marionette from 'backbone.marionette';

import routeManager from './routeManager.js';
import Ctx from './common/context.js';
import message from './models/message.js';
import idea from './models/idea.js';
import agent from './models/agents.js';

/**
 * The Router will forward existing URLs to various handlers according to those routes
 * Keep in sync with :py:class:`assembl.lib.frontend_urls.FrontendUrls`
 * @class app.router.Router
 * @extends Marionette.AppRouter
 */
var Router = Marionette.AppRouter.extend({
  controller: routeManager,

  //Note:  This should match with assembl/lib/frontend_url.py
  discussionRoutes: {
    "": "home",
    "edition": "edition",
    "partners": "partners",
    "notifications": "notifications",
    "settings": "settings",
    "timeline": "timeline",
    "about": "about",
    "discussion_preferences": "adminDiscussionPreferences",
    "permissions": "adminDiscussionPermissions",
    "sentrytest": "sentryTest",
    "user/notifications": "userNotifications",
    "user/profile": "profile",
    "user/account": "account",
    "user/tos": "tos",
    "user/discussion_preferences": "userDiscussionPreferences",
    "posts/*id": "post",
    "idea/*id": "idea",
    "widget/:id(/:result)": "widgetInModal",
    "profile/*id": "user",
    "G/*path": "groupSpec",
    "*actions": "defaults"
  },

  adminRoutes: {
    "global_preferences": "adminGlobalPreferences",
  },

});

Router.prototype.appRoutes = (Ctx.isAdminApp())?
    Router.prototype.adminRoutes:Router.prototype.discussionRoutes;

// Monkey patch ensures that shared knowledge is in a single file
// TODO: improve.
message.Model.prototype.routerBaseUrl = "posts/";
idea.Model.prototype.routerBaseUrl = "idea/";
agent.Model.prototype.routerBaseUrl = "profile/";

export default Router;
