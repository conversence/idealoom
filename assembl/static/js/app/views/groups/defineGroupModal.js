/**
 * 
 * @module app.views.groups.defineGroupModal
 */

import Marionette from 'backbone.marionette';

import $ from 'jquery';
import _ from 'underscore';
import Backbone from 'backbone';
import BackboneModal from 'backbone.modal';
import IdeaLoom from '../../app.js';
import Ctx from '../../common/context.js';
import GroupSpec from '../../models/groupSpec.js';
import CollectionManager from '../../common/collectionManager.js';
import PanelSpecTypes from '../../utils/panelSpecTypes.js';
import viewsFactory from '../../objects/viewsFactory.js';
import Permissions from '../../utils/permissions.js';
import i18n from '../../utils/i18n.js';
import Roles from '../../utils/roles.js';
import Widget from '../../models/widget.js';
import WidgetLinks from '../widgetLinks.js';

/**
 * 
 * @class app.views.groups.defineGroupModal.DefineGroupModal
 */
class DefineGroupModal extends Backbone.Modal.extend({
  template: _.template($('#tmpl-create-group').html()),
  className: 'generic-modal popin-wrapper',
  cancelEl: '.close, .btn-cancel',

  events: {
    'click .js_selectItem': 'selectItem',
    'click .js_createGroup': 'createGroup'
  }
}) {
  serializeData() {
    var displayCIDashboard = Ctx.getPreferences().show_ci_dashboard;
    var numLowerPanels = displayCIDashboard ? 4 : 3;
    return {
      PanelSpecTypes: PanelSpecTypes,
      displayCIDashboard: displayCIDashboard,
      numLowerPanels: numLowerPanels,
      panelOrder: Ctx.getPreferences().simple_view_panel_order
    };
  }

  initialize(options) {
    this.groupSpecsP = options.groupSpecsP;
    this.$('.bbm-modal').addClass('popin');
  }

  selectItem(e) {
    var elm = $(e.currentTarget);
    var item = elm.parent().attr('data-view');

    elm.parent().toggleClass('is-selected');

    if (elm.parent().hasClass('is-selected')) {
      switch (item) {
        case PanelSpecTypes.NAV_SIDEBAR.id:
          this.disableView([PanelSpecTypes.TABLE_OF_IDEAS, PanelSpecTypes.SYNTHESIS_EDITOR, PanelSpecTypes.CLIPBOARD, PanelSpecTypes.MESSAGE_LIST, PanelSpecTypes.IDEA_PANEL, PanelSpecTypes.CI_DASHBOARD_CONTEXT]);
          break;
        case PanelSpecTypes.SYNTHESIS_EDITOR.id:
          this.disableView([PanelSpecTypes.TABLE_OF_IDEAS, PanelSpecTypes.NAV_SIDEBAR]);
          this.enableView([PanelSpecTypes.IDEA_PANEL, PanelSpecTypes.MESSAGE_LIST]);
          break;
        case PanelSpecTypes.TABLE_OF_IDEAS.id:
          this.disableView([PanelSpecTypes.SYNTHESIS_EDITOR, PanelSpecTypes.NAV_SIDEBAR]);
          this.enableView([PanelSpecTypes.IDEA_PANEL, PanelSpecTypes.MESSAGE_LIST]);
          break;
      }

    } else {
      switch (item) {
        case PanelSpecTypes.NAV_SIDEBAR.id:
          this.enableView([PanelSpecTypes.TABLE_OF_IDEAS, PanelSpecTypes.SYNTHESIS_EDITOR, PanelSpecTypes.CLIPBOARD, PanelSpecTypes.CI_DASHBOARD_CONTEXT]);
          break;
        case PanelSpecTypes.SYNTHESIS_EDITOR.id:
          this.enableView([PanelSpecTypes.TABLE_OF_IDEAS, PanelSpecTypes.NAV_SIDEBAR]);
          this.disableView([PanelSpecTypes.IDEA_PANEL, PanelSpecTypes.MESSAGE_LIST]);
          break;
        case PanelSpecTypes.TABLE_OF_IDEAS.id:
          this.disableView([PanelSpecTypes.IDEA_PANEL, PanelSpecTypes.MESSAGE_LIST]);
          this.enableView([PanelSpecTypes.SYNTHESIS_EDITOR, PanelSpecTypes.NAV_SIDEBAR]);
          break;
      }
    }
  }

  disableView(items) {
    items.forEach(function(item) {
      var panel = $(".itemGroup[data-view='" + item.id + "']");
      panel.removeClass('is-selected');
      panel.addClass('is-disabled');
    });
  }

  enableView(items) {
    items.forEach(function(item) {
      var panel = $(".itemGroup[data-view='" + item.id + "']");
      panel.removeClass('is-disabled');
    });
  }

  createGroup() {
    var items = [];
    var that = this;
    var hasNavSide = false;

    if ($('.itemGroup').hasClass('is-selected')) {

      $('.itemGroup.is-selected').each(function() {
        var item = $(this).attr('data-view');
        items.push({type: item});

        if (item === 'navSidebar') {
          hasNavSide = true;
        }
      });
      this.groupSpecsP.done(function(groupSpecs) {
        var groupSpec = new GroupSpec.Model(
            {'panels': items}, {'parse': true, 'viewsFactory': viewsFactory});
        groupSpecs.add(groupSpec);
      });

      setTimeout(function() {
        that.scrollToRight();

        if (hasNavSide) {
          IdeaLoom.other_vent.trigger('DEPRECATEDnavigation:selected', 'about');
        }

        that.$el.unbind();
        that.$el.remove();
      }, 100);
    }
  }

  scrollToRight() {
    var right = $('.groupsContainer').width();
    $('.groupsContainer').animate({
      scrollLeft: right
    }, 1000);
  }
}

export default DefineGroupModal;
