/**
 * 
 * @module app.views.groups.modalGroup
 */

import Backbone from 'backbone';
import _ from 'underscore';
import $ from 'jquery';
import IdeaLoom from '../../app.js';
import Ctx from '../../common/context.js';
import i18n from '../../utils/i18n.js';
//import panelSpec from '../../models/panelSpec';
//import PanelSpecTypes from '../../utils/panelSpecTypes';
//import viewsFactory from '../../objects/viewsFactory';
import groupSpec from '../../models/groupSpec';
import GroupContainer from '../groups/groupContainer';
import panelSpec from '../../models/panelSpec.js';
import PanelSpecTypes from '../../utils/panelSpecTypes.js';
import viewsFactory from '../../objects/viewsFactory';

/**
 * @class app.views.groups.modalGroup.ModalGroupView
 */
class ModalGroupView extends Backbone.Modal.extend({
  template: _.template($('#tmpl-groupModal').html()),
  className: 'panelGroups-modal popin-wrapper',
  cancelEl: '.close, .js_close',
  keyControl: false,
  title: null,

  events: {
    'submit #partner-form':'validatePartner'
  }
}) {
  /**
   * A modal group has only a single group
   */
  getGroup() {
    if (!this.groupsView.isRendered() && !this.groupsView.isDestroyed()) {
      //so children will work
      this.groupsView.render();
    }

    var firstGroup = this.groupsView.children.first();
    if (!firstGroup) {
      console.log(this.groupsView.children);
      throw new Error("There is no group in the modal!");
    }

    return firstGroup;
  }

  /** Takes a groupSpec as model
   * 
   */
  initialize(options) {
    if (options && "title" in options)
      this.title = options.title;
    this.$('.bbm-modal').addClass('popin');
    var groupSpecCollection = new groupSpec.Collection([this.model]);
    this.groupsView = new GroupContainer({
      collection: groupSpecCollection
    });
  }

  onRender() {
    if (!this.groupsView.isDestroyed()) {
      if (!this.groupsView.isRendered()) {
        this.groupsView.render();
      }

      this.$('.popin-body').html(this.groupsView.el);
    }
  }

  serializeData() {
    return {
      "title": this.title
    };
  }

  getGroupContentView() {
    console.log("Looking for model:", this.model, "in:", _.clone(this.groupsView.children.indexByModel));
    console.log("Result: ", this.groupsView.children.findByModel(this.groupSpecModel))
    return this.groupsView.children.findByModel(this.groupSpecModel);
  }
}

/**
 * @param title:  title of the modal
 * @param filters: an array of objects:
 *   filterDef:  a member of availableFilters in postFilter.js
 *   value:  the value to be filtered
 * @return: {modal: modal, messagePanel: messagePanel}
 *  modal is a fully configured instance of ModalGroup.
 */
var filteredMessagePanelFactory = function(modal_title, filters) {
  var defaults = {
      panels: new panelSpec.Collection([
                                        {type: PanelSpecTypes.MESSAGE_LIST.id, minimized: false}
                                        ],
                                        {'viewsFactory': viewsFactory })
  };
  var groupSpecModel = new groupSpec.Model(defaults);
  var modal = new ModalGroupView({"model": groupSpecModel, "title": modal_title});
  var group = modal.getGroup();

  var messagePanel = group.findViewByType(PanelSpecTypes.MESSAGE_LIST);
  messagePanel.setViewStyle(messagePanel.ViewStyles.THREADED, true)
  _.each(filters, function(filter){
    messagePanel.currentQuery.initialize();
    //messagePanel.currentQuery.addFilter(this.messageListView.currentQuery.availableFilters.POST_IS_DESCENDENT_OR_ANCESTOR_OF_POST, this.model.id);
    messagePanel.currentQuery.addFilter(filter.filterDef, filter.value);
  });

  //console.log("About to manually trigger messagePanel render");
  //Re-render so the changes above are taken into account
  messagePanel.render();
  return {modal: modal, messageList: messagePanel};
}
export default { 
    View: ModalGroupView,
    filteredMessagePanelFactory: filteredMessagePanelFactory
  }
