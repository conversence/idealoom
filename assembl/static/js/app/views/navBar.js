/**
 * 
 * @module app.views.navBar
 */

import Marionette from 'backbone.marionette';

import Backbone from 'backbone';
import BackboneModal from 'backbone.modal';
import Promise from 'bluebird';
import $ from 'jquery';
import _ from 'underscore';
import IdeaLoom from '../app.js';
import Ctx from '../common/context.js';
import GroupSpec from '../models/groupSpec.js';
import CollectionManager from '../common/collectionManager.js';
import PanelSpecTypes from '../utils/panelSpecTypes.js';
import viewsFactory from '../objects/viewsFactory.js';
import RoleModels from '../models/roles.js';
import Permissions from '../utils/permissions.js';
import i18n from '../utils/i18n.js';
import Roles from '../utils/roles.js';
import Widget from '../models/widget.js';
import DefineGroupModal from './groups/defineGroupModal.js';
import WidgetLinks from './widgetLinks.js';
import Analytics from '../internal_modules/analytics/dispatcher.js';
import StatisticsModal from './modals/discussionStatisticsModal.js';
import LoaderView from './loaderView.js';
import AgentViews from './agent.js';

class navBarLeft extends Marionette.View.extend({
  template: '#tmpl-navBarLeft',
  className: 'navbar-left',

  ui: {
    discussionStatistics: ".js_discussion_statistics",
  },

  regions: {
    widgetMenuConfig: ".navbar-widget-configuration-links",
    widgetMenuCreation: ".navbar-widget-creation-links"
  },

  events: {
    'click @ui.discussionStatistics': 'discussionStatistics',
  }
}) {
  initialize(options) {
    this.isAdminDiscussion = Ctx.getCurrentUser().can(Permissions.ADMIN_DISCUSSION);
  }

  onRender() {
    var that = this;
    this.listenTo(IdeaLoom.socket_vent, 'socket:open', function() {
      that.$('#onlinedot').addClass('is-online');
    });
    this.listenTo(IdeaLoom.socket_vent, 'socket:close', function() {
      that.$('#onlinedot').removeClass('is-online');
    });

    // show a dropdown to admins, for widgets management
    // TODO: add to the dropdown the "discussion permissions" and "discussion parameters" options => so this IdeaWidgets view would only add <li>s to a dropdown which will be built elsewhere
    if (this.isAdminDiscussion && !Ctx.isAdminApp()) {
      // find root idea
      var collectionManager = new CollectionManager();
      Promise.join(collectionManager.getAllIdeasCollectionPromise(),
          collectionManager.getAllWidgetsPromise(),
          collectionManager.getUserLanguagePreferencesPromise(Ctx),
        function(allIdeasCollection, widgets, ulp) {
        if(!that.isDestroyed()) {
          var rootIdea = allIdeasCollection.getRootIdea();
          if (rootIdea) {
            var confWidgets = new Widget.WidgetSubset([], {
              parent: widgets,
              context: Widget.Model.prototype.DISCUSSION_MENU_CONFIGURE_CTX,
              idea: rootIdea});
            if (confWidgets.length) {
              var configuration = new WidgetLinks.WidgetLinkListView({collection: confWidgets});
              that.showChildView('widgetMenuConfig', configuration);
            }
            var creation = new WidgetLinks.WidgetLinkListView({
              collection: Widget.globalWidgetClassCollection,
              context: Widget.Model.prototype.DISCUSSION_MENU_CREATE_CTX,
              translationData: ulp,
              idea: rootIdea
            });
            that.showChildView('widgetMenuCreation', creation);
          } else {
            console.log("rootIdea problem: ", rootIdea);
            this.$el.find(".discussion-title-dropdown").addClass("hidden");
          }
        }
      });
    } else {
      this.$el.find(".discussion-title-dropdown").addClass("hidden");
    }
  }

  serializeData() {
    return {
      isAdminDiscussion: this.isAdminDiscussion,
      canAccessStatistics: Ctx.getCurrentUser().can(Permissions.DISC_STATS),
      discussionSettings: '/' + Ctx.getDiscussionSlug() + '/edition',
      discussionPermissions: '/admin/permissions/discussion/' + Ctx.getDiscussionId(),
    };
  }

  discussionStatistics() {
      var modal = new StatisticsModal();
      $('#slider').html(modal.render().el);
  }
}

class navBarRight extends LoaderView.extend({
  template: '#tmpl-navBarRight',
  className: 'navbar-right',

  ui: {
    currentLocal: '.js_setLocale',
    joinDiscussion: '.js_joinDiscussion',
    needJoinDiscussion: '.js_needJoinDiscussion',

  },

  events: {
    'click @ui.currentLocal': 'setLocale',
    'click @ui.joinDiscussion': 'joinPopin',
    'click @ui.needJoinDiscussion': 'needJoinDiscussion'
  },

  regions: {
    userAvatarRegion: '.user-avatar-container'
  }
}) {
  initialize(options) {
    var that = this;
    var collectionManager = new CollectionManager();

    if (Ctx.getDiscussionId() && Ctx.getCurrentUserId()) {
      this.setLoading(true);
      collectionManager.getMyLocalRoleCollectionPromise()
      .then(function(localRoles) {
        that.localRoles = localRoles;
        that.isUserSubscribedToDiscussion = localRoles.isUserSubscribedToDiscussion();
        that.setLoading(false);

        that.render();
        // that.onBeforeRender();

        if (localRoles) {
          that.listenTo(localRoles, 'remove add', function(model) {
            that.isUserSubscribedToDiscussion = localRoles.isUserSubscribedToDiscussion();
            that.render();
          });
        }
      });
    }
    else {
      this.isUserSubscribedToDiscussion = false;
    }
  }

  onRender() {
    if(this.isLoading()) {
      return {};
    }

    var userAvatarView = new AgentViews.AgentAvatarView({
      model: Ctx.getCurrentUser(),
      avatarSize: 25
    });
    if (!Ctx.getCurrentUser().isUnknownUser()) {
        this.showChildView('userAvatarRegion', userAvatarView);
    }
  }

  serializeData() {
    if(this.isLoading()) {
      return {};
    }
    var retval = {}
    return {
      Ctx: Ctx,
      isUserSubscribedToDiscussion: this.isUserSubscribedToDiscussion,
      canSubscribeToDiscussion: Ctx.getCurrentUser().can(Permissions.SELF_REGISTER),
      isAdminDiscussion: Ctx.getCurrentUser().can(Permissions.ADMIN_DISCUSSION)
    }
  }

  templateContext() {
    return {
      urlNotifications: function() {
        return '/' + Ctx.getDiscussionSlug() + '/user/notifications';
      },
    }
  }

  setLocale(e) {
    var lang = $(e.target).attr('data-locale');
    Ctx.setLocale(lang);
  }

  needJoinDiscussion() {
    if (!this._store.getItem('needJoinDiscussion')) {
      this._store.setItem('needJoinDiscussion', true);
    }
    var analytics = Analytics.getInstance();
    analytics.trackEvent(analytics.events.JOIN_DISCUSSION_CLICK);
  }

  joinPopin() {
    var analytics = Analytics.getInstance();
    IdeaLoom.other_vent.trigger('navBar:joinDiscussion');
    analytics.trackEvent(analytics.events.JOIN_DISCUSSION_CLICK);
  }
}

class navBar extends Marionette.View.extend({
  template: '#tmpl-navBar',
  tagName: 'nav',
  className: 'navbar navbar-default',

  ui: {
    groups: '.js_addGroup',
    expertInterface: '.js_switchToExpertInterface',
    simpleInterface: '.js_switchToSimpleInterface'
  },

  events: {
    'click @ui.groups': 'addGroup',
    'click @ui.expertInterface': 'switchToExpertInterface',
    'click @ui.simpleInterface': 'switchToSimpleInterface'
  },

  regions: {
      'navBarLeft':'#navBarLeft',
      'navBarRight':'#navBarRight'
    }
}) {
  initialize() {
    this._store = window.localStorage;
    this.showPopInDiscussion();
    this.showPopInOnFirstLoginAfterAutoSubscribeToNotifications();
    this.listenTo(IdeaLoom.other_vent, 'navBar:subscribeOnFirstPost', this.showPopInOnFirstPost);
    this.listenTo(IdeaLoom.other_vent, 'navBar:joinDiscussion', this.joinDiscussion)
  }

  serializeData() {
    return {
      Ctx: Ctx
    }
  }

  onRender() {
    var navRight = new navBarRight();
    this.showChildView('navBarRight', navRight);
    this.showChildView('navBarLeft', new navBarLeft());
  }

  switchToExpertInterface(e) {
    Ctx.setInterfaceType(Ctx.InterfaceTypes.EXPERT);
  }

  switchToSimpleInterface(e) {
    Ctx.setInterfaceType(Ctx.InterfaceTypes.SIMPLE);
  }

  addGroup() {
    var collectionManager = new CollectionManager();
    var groupSpecsP = collectionManager.getGroupSpecsCollectionPromise(viewsFactory);

    IdeaLoom.rootView.showChildView('slider', new DefineGroupModal({groupSpecsP: groupSpecsP}));
  }

  /**
    * @param {string|null} popinType: null, 'first_post', 'first_login_after_auto_subscribe_to_notifications'
    */
  joinDiscussion(evt, popinType) {
    var self = this;
    var collectionManager = new CollectionManager();

    var model = new Backbone.Model({
      notificationsToShow: null
    });

    var modalClassName = 'generic-modal popin-wrapper modal-joinDiscussion';
    var modalTemplate = _.template($('#tmpl-joinDiscussion').html());

    if (popinType == 'first_post') {
      modalClassName = 'generic-modal popin-wrapper modal-firstPost';
      modalTemplate = _.template($('#tmpl-firstPost').html());
    }
    else if (popinType == 'first_login_after_auto_subscribe_to_notifications') {
      modalClassName = 'generic-modal popin-wrapper modal-firstPost';
      modalTemplate = _.template($('#tmpl-firstLoginAfterAutoSubscribeToNotifications').html());
    }

    Promise.join(
      collectionManager.getNotificationsDiscussionCollectionPromise(),
      collectionManager.getMyLocalRoleCollectionPromise(),
      function(discussionNotifications, localRoles) {
        var isUserSubscribedToDiscussion = localRoles.isUserSubscribedToDiscussion();
        model.notificationsToShow = _.filter(discussionNotifications.models, function(m) {
          // keep only the list of notifications which become active when a user follows a discussion
          return (m.get('creation_origin') === 'DISCUSSION_DEFAULT') && (m.get('status') === 'ACTIVE');
        });

        // we show the popin only if there are default notifications
        // Actually we want the modal either way; commenting the condition for now. MAP
        //if ( model.notificationsToShow && model.notificationsToShow.length ){

        class Modal extends Backbone.Modal.extend({
          template: modalTemplate,
          className: modalClassName,
          cancelEl: '.close, .js_close',
          submitEl: '.js_subscribe',
          model: model
        }) {
          initialize() {
            var that = this;
            this.$('.bbm-modal').addClass('popin');
            var analytics = Analytics.getInstance();
            var previousPage = analytics.getCurrentPage();

            this.returningPage = previousPage;
            analytics.changeCurrentPage(analytics.pages.NOTIFICATION);
          }

          serializeData() {
            return {
              i18n: i18n,
              notificationsToShow: model.notificationsToShow,
              urlNotifications: '/' + Ctx.getDiscussionSlug() + '/user/notifications'
            }
          }

          submit(ev) {
            var that = this;

            if (Ctx.getDiscussionId() && Ctx.getCurrentUserId() && !isUserSubscribedToDiscussion) {

              var LocalRolesUser = new RoleModels.localRoleModel({
                role: Roles.PARTICIPANT,
                discussion: 'local:Discussion/' + Ctx.getDiscussionId()
              });
              LocalRolesUser.save(null, {
                success: function(model, resp) {
                  var analytics = Analytics.getInstance();
                  analytics.trackEvent(analytics.events.JOIN_DISCUSSION);

                  // TODO: Is there a simpler way to do this? MAP
                  self.getRegion('navBarRight').currentView.ui.joinDiscussion.css('visibility', 'hidden');
                  self._store.removeItem('needJoinDiscussion');

                  // reload user data and its permissions (so for example now when he clicks on the "reply" button of a message, it should not show "Before you can reply to this message..." anymore)
                  try { // we try to be a good Single Page Application and update user data without reloading the whole page
                    Ctx.updateCurrentUser();
                  } catch (e) { // but if it does not work, we reload the page
                    console.log("Error while reloading user data: " + e.message);
                    location.reload();
                  }
                },
                error: function(model, resp) {
                  console.error('ERROR: joinDiscussion->subscription', resp);
                }
              })
            }
          }

          cancel() {
            self._store.removeItem('needJoinDiscussion');
            var analytics = Analytics.getInstance();
            analytics.trackEvent(analytics.events.JOIN_DISCUSSION_REFUSED);
            analytics.changeCurrentPage(this.returningPage, {default: true}); //if page is null, go back to / page
          }
        }

        IdeaLoom.rootView.showChildView('slider', new Modal());

        //}
      }

        );
  }

  showPopInOnFirstPost() {
    this.joinDiscussion(null, 'firstPost');
  }

  showPopInOnFirstLoginAfterAutoSubscribeToNotifications() {
    if (typeof first_login_after_auto_subscribe_to_notifications != 'undefined'
        && first_login_after_auto_subscribe_to_notifications == true)
    {
      this.joinDiscussion(null, 'first_login_after_auto_subscribe_to_notifications');
    }
  }

  showPopInDiscussion() {
    var needPopIn = this._store.getItem('needJoinDiscussion');
    if (needPopIn && Ctx.getCurrentUserId() && this.roles.get('role') === null) {
      this.joinDiscussion();
    } else {
      this._store.removeItem('needJoinDiscussion');
    }
  }
}

export default navBar;
