/**
 * 
 * @module app.views.groups.groupContent
 */

import Marionette from 'backbone.marionette';

import Ctx from '../../common/context.js';
import i18n from '../../utils/i18n.js';
import panelSpec from '../../models/panelSpec.js';
import BasePanel from '../basePanel.js';
import PanelWrapper from './panelWrapper.js';
import PanelSpecTypes from '../../utils/panelSpecTypes.js';
import Analytics from '../../internal_modules/analytics/dispatcher.js';
import Storage from '../../objects/storage.js';
import UserCustomData from '../../models/userCustomData.js';


/** Represents the entire content of a single panel group
* @class  app.views.groups.groupContent.groupContent
*/
class groupContentBody extends Marionette.CollectionView.extend({
  className: 'groupBody',
  childView: PanelWrapper
}) {
  initialize(options) {
    this.parent = options.parent;
  }

  /**
   * Tell the panelWrapper which view to put in its contents
   */
  childViewOptions(child) {
    return {
      groupContent: this.parent,
      contentSpec: child,
    };
  }
}

/** Represents the entire content of a single panel group
* @class  app.views.groups.groupContent.groupContent
*/
class groupContent extends Marionette.View.extend({
  template: "#tmpl-groupContent",
  className: "groupContent",

  regions: {
    body: {
      el: '.groupBody',
      replaceElement: true,
    },
  },

  panel_borders_size: 1,

  events: {
    'click .js_closeGroup': 'closeGroup'
  }
}) {
  initialize(options) {
    this.collection = this.model.get('panels');
    this.groupContainer = options['groupContainer'];
    this.body = new groupContentBody({
      collection: this.collection,
      parent: this,
    });
  }

  onRender() {
    if (!this.isDestroyed()) {
      this.showChildView('body', this.body);
    }
  }

  onAttach() {
    if (!this.isDestroyed()) {
      var navView = this.findViewByType(PanelSpecTypes.NAV_SIDEBAR);
      if (navView) {
        navView.setViewByName(this.model.get('navigationState'), null);
      }
    }
  }

  serializeData() {
    return {
      "Ctx": Ctx
    };
  }

  /**
   * Set the given Idea as the current one to be edited
   * @param  {Idea} idea
   * @param  {boolean} noResetState: Do not change panels. Rare.
   * @param  {string} reason: deprecated. Should go to analytics?
   */
  setCurrentIdea(idea, noResetState, reason) {
    if (idea !== this._getCurrentIdea()) {
      var analytics = Analytics.getInstance();
      if (idea !== null) {
        analytics.changeCurrentPage(analytics.pages.IDEA);
      } else {
        // If idea is null, assume we are focussed on the messages
        analytics.changeCurrentPage(analytics.pages.MESSAGES);
      }
      this.model.get('states').at(0).set({currentIdea: idea}, {validate: true});
    } else if (idea === null) {
      // Hack for pseudo-ideas, so changes are seen and panel closes
      // Simulate a change event on that model's attribute, to be received by listener in ideaPanel
      this.trigger("change:pseudoIdea", null);
    } else {
      return;
    }
    if (!noResetState) {
      this.NavigationResetDebateState();
    }
  }

  /**
   * @return: undefined if no idea was set yet.
   * null if it was explicitely set to no idea.
   *
   */
  _getCurrentIdea() {
      return this.model.get('states').at(0).get('currentIdea');
    }

  closeGroup() {
    this.applyUserCustomDataChangesOnGroupClose();
    this.model.collection.remove(this.model);
    this.groupContainer.resizeAllPanels(true);
  }

  findNavigationSidebarPanelSpec() {
    return this.model.findNavigationSidebarPanelSpec();
  }

  isSimpleInterface() {
    if (this.findNavigationSidebarPanelSpec()) {
      return true;
    } else {
      return false;
    }
  }

  /**
   * Specific to the simple interface. Go back to default view.
   * As things stand, default view is debate state with last idea selected.
   */
  NavigationResetDefaultState() {
    return this.NavigationResetDebateState();
  }

  /**
   * Specific to the simple interface.  Does nothing if there is no
   * navigation sidebar panel in this group.
   * If there is, get's it back to the default debate view
   */
  NavigationResetDebateState() {
    if (!this.isDestroyed()) {  //Because this is called from outside the view
      if (this.findNavigationSidebarPanelSpec()) {
        this.model.set('navigationState', 'debate');
        this.SimpleUIResetMessageAndIdeaPanelState(this._getCurrentIdea());
      }
    }
  }

  NavigationResetAboutState() {
    if (!this.isDestroyed()) {  //Because this is called from outside the view
      var nav = this.findNavigationSidebarPanelSpec();
      if (nav) {
        this.model.set('navigationState', 'about');
        this.ensureOnlyPanelsVisible(PanelSpecTypes.DISCUSSION_CONTEXT);
      }
    }
  }

  NavigationResetSynthesisMessagesState(synthesisInNavigationPanel) {
    if (!this.isDestroyed()) {  //Because this is called from outside the view
      if (this.findNavigationSidebarPanelSpec()) {
        this.setCurrentIdea(null);
        this.ensureOnlyPanelsVisible(PanelSpecTypes.MESSAGE_LIST, PanelSpecTypes.IDEA_PANEL);
        this.ensurePanelsHidden(PanelSpecTypes.IDEA_PANEL);
      }
    }
  }

  NavigationResetVisualizationState(url) {
    if (!this.isDestroyed()) {  //Because this is called from outside the view
      var nav = this.findNavigationSidebarPanelSpec();
      if (nav) {
        this.model.set('navigationState', 'visualizations');
        this.ensureOnlyPanelsVisible(PanelSpecTypes.EXTERNAL_VISUALIZATION_CONTEXT);
        var vizPanel = this.findViewByType(PanelSpecTypes.EXTERNAL_VISUALIZATION_CONTEXT);
        vizPanel.setUrl(url);
      }
    }
  }

  SimpleUIResetMessageAndIdeaPanelState(idea) {
    if (!this.isDestroyed()) {  //Because this is called from outside the view
      var preferences = Ctx.getPreferences();
      // defined here and in collectionManager.getGroupSpecsCollectionPromise
      if (preferences.simple_view_panel_order === "NMI") {
          this.ensureOnlyPanelsVisible(PanelSpecTypes.MESSAGE_LIST, PanelSpecTypes.IDEA_PANEL);
      } else {
          this.ensureOnlyPanelsVisible(PanelSpecTypes.IDEA_PANEL, PanelSpecTypes.MESSAGE_LIST);
      }
    }
  }

  /**
   * @params panelSpecTypes
   */
  removePanels(...args) {
    this.model.removePanels(...args);
  }

  addPanel(options, position) {
    this.model.addPanel(options, position);
  }

  /**
   * create the model (and corresponding view) if it does not exist.
   */
  ensurePanel(options, position) {
    this.model.ensurePanel(options, position);
  }

  /* Typenames are available in the panelType class attribute of each
   * panel class
   *
   */
  findPanelWrapperByType(panelSpecType) {
    var model = this.model.getPanelSpecByType(panelSpecType);
    if (model !== undefined) {
      var view = this.body.children.findByModel(model);
      if (view == null) {
        return undefined;
      }
      else {
        return view;
      }
    }
    return undefined;
  }

  findViewByType(panelSpecType) {
    var retval = undefined;
    var wrapper = this.findPanelWrapperByType(panelSpecType);

    if (wrapper != null) {
      if (wrapper.getRegion('contents') === undefined) {
        throw new Error("PanelWrapper doesn't have any content");
      }

      retval = wrapper.getRegion('contents').currentView;
    }
    return retval;
  }

  getNavigationPanel(panelSpecType) {
    var retval = undefined;
    var navigationPanelSpec = this.model.findNavigationPanelSpec();
    if (navigationPanelSpec) {
      retval = this.findViewByType(navigationPanelSpec);
    }
    return retval;
  }

  /** 
   * ensure only the listed panels, are visible
   * However, all panels are created if necessary
   * @params list of panel names
   */
  ensureOnlyPanelsVisible() {
    var that = this;
    var args = Array.prototype.slice.call(arguments);
    var panels = this.model.get('panels');
    // add missing panels
    this.model.ensurePanelsAt(args, 1);
    // show and hide panels
    _.each(this.model.get('panels').models, function(aPanelSpec) {
      var panelSpecType = aPanelSpec.getPanelSpecType();
      if (panelSpecType === PanelSpecTypes.NAV_SIDEBAR)
          return;
      var view = that.body.children.findByModel(aPanelSpec);
      if (!view)
          return;
      var shouldBeVisible = _.find(args, function(arg) {
        return panelSpecType === arg
      }) !== undefined;
      aPanelSpec.set('hidden', !shouldBeVisible);
    });
  }

  /**
   * Ensure all listed panels are visible, and in the order listed
   * creating them if necessary.
   * Does not touch visibility of PanelSpecTypes.NAV_SIDEBAR, but creates
   * it if absent
   * @params list of PanelSpecTypes
   */
  ensurePanelsVisible() {
    var that = this;
    var args = Array.prototype.slice.call(arguments);
    var panels = this.model.get('panels');
    // add missing panels
    this.model.ensurePanelsAt(args, 1);
    // show and hide panels
    var panelSpecsToMakeVisible = this.model.get('panels').models.filter(function(aPanelSpec) {
      var panelSpecType = aPanelSpec.getPanelSpecType();
      return _.contains(args, panelSpecType);
    });
    if (_.size(args) !== _.size(panelSpecsToMakeVisible)) {
      console.log(args, panelSpecsToMakeVisible);
      throw new Error("Error, unable to find all panels to make visible");
    }
    _.each(panelSpecsToMakeVisible, function(aPanelSpec) {
      aPanelSpec.set('hidden', false);
    });
  }

  /**
   * Ensure all listed panels are hidden if present
   * Skips PanelSpecTypes.NAV_SIDEBAR
   * @params list of panel names
   */
  ensurePanelsHidden() {
    var that = this;
    var args = Array.prototype.slice.call(arguments);
    var panels = this.model.get('panels');
    // show and hide panels
    _.each(this.model.get('panels').models, function(aPanelSpec) {
      var panelSpecType = aPanelSpec.getPanelSpecType();
      if (panelSpecType === PanelSpecTypes.NAV_SIDEBAR) {
        return;
      }
      var shouldBeHidden = _.find(args, function(arg) {
        return panelSpecType === arg
      }) !== undefined;
      if (shouldBeHidden) {
        aPanelSpec.set('hidden', true);
      }
    });
  }

  getGroupStoragePrefix() {
    var groupContent = this;
    var groupContentIndexInGroupContainer = groupContent.groupContainer.collection.indexOf(groupContent.model);
    var storagePrefix = Storage.getStoragePrefix() + "_group_" + groupContentIndexInGroupContainer;
    return storagePrefix;
  }

  /**
   * When the user closes a panel group, all UserCustomData entries which keys contain the index of the group have to be renamed with their new index.
   */
  applyUserCustomDataChangesOnGroupClose() {
    if (!Ctx.isUserConnected()){
      return;
    }
    var groupContent = this;
    var groupContentIndexInGroupContainer = groupContent.groupContainer.collection.indexOf(groupContent.model);
    var sz = groupContent.groupContainer.collection.length;
    var storagePrefix = Storage.getStoragePrefix() + "_group_";
    var storageSuffix = "_table_of_ideas_collapsed_state";
    var i;
    if ( groupContentIndexInGroupContainer < sz-1 ){
      var tableOfIdeasCollapsedStateModels = [];
      var tableOfIdeasCollapsedStatePromises = [];

      for ( i = 0; i < groupContentIndexInGroupContainer; ++i ){
        tableOfIdeasCollapsedStatePromises[i] = Promise.resolve(true);
      }
      for ( i = groupContentIndexInGroupContainer; i < sz ; ++i ){
        tableOfIdeasCollapsedStateModels[i] = new UserCustomData.Model({
          id: storagePrefix + i + storageSuffix
        });
        tableOfIdeasCollapsedStatePromises[i] = tableOfIdeasCollapsedStateModels[i].fetch();
      }
      Promise.all(tableOfIdeasCollapsedStatePromises).then(function(models){
        for ( i = groupContentIndexInGroupContainer; i < sz; ++i ){
          console.log("tableOfIdeasCollapsedStateModels[i]: ", tableOfIdeasCollapsedStateModels[i]);
          // Move table of ideas collapsed state of group number i to one of group number i-1
          tableOfIdeasCollapsedStateModels[i].set("id", storagePrefix + (i-1) + storageSuffix);
          tableOfIdeasCollapsedStateModels[i].save();
        }
      });
    }
  }
}

export default groupContent;
