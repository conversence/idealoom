/**
 * 
 * @module app.views.user.tos
 */

import Marionette from 'backbone.marionette';

import $ from 'jquery';
import _ from 'underscore';
import Promise from 'bluebird';
import Agents from '../../models/agents.js';
import i18n from '../../utils/i18n.js';
import UserNavigationMenu from './userNavigationMenu.js';
import Ctx from '../../common/context.js';
import CollectionManager from '../../common/collectionManager.js';
import Growl from '../../utils/growl.js';

class UserTOS extends Marionette.View.extend({
  template: '#tmpl-userTOS',
  className: 'admin-tos',

  ui: {
    accept: '#accept-button',
    tos: '#js_tos',
  },

  regions: {
    navigationMenuHolder: '.navigation-menu-holder'
  },

  modelEvents: {
    'change sync': 'render'
  },

  events: {
    'click @ui.accept': 'acceptTos'
  }
}) {
  initialize() {
    this.model = Ctx.getCurrentUser();
    var discussionSettings = Ctx.getPreferences();
    var collectionManager = new CollectionManager();
    var terms_ls = discussionSettings.terms_of_service || {};
    var terms = terms_ls[Ctx.getLocale()] || _.first(_.values(terms_ls)) || '';
    this.terms = terms;
  }

  serializeData() {
    var discussionSettings = Ctx.getPreferences();
    return {
      profile: this.model,
      tos: this.terms,
      accepted: this.model.get('accepted_tos_version') == discussionSettings.tos_version,
    }
  }

  onRender() {
    // this is in onRender instead of onBeforeRender because of the modelEvents
    var menu = new UserNavigationMenu({selectedSection: "tos"});
    this.showChildView('navigationMenuHolder', menu);
  }

  acceptTos(e) {
    e.preventDefault();

    var discussionSettings = Ctx.getPreferences();
    this.model.set({ accepted_tos_version: discussionSettings.tos_version});

    this.model.save(null, {
      success: function(model, resp) {
        Growl.showBottomGrowl(Growl.GrowlReason.SUCCESS, i18n.gettext('Thank you for accepting!'));
      },
      error: function(model, resp) {
        Growl.showBottomGrowl(Growl.GrowlReason.ERROR, i18n.gettext('We could not register your acceptance.'));
      }
    })
  }
}

export default UserTOS;
