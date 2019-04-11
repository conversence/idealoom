import Marionette from 'backbone.marionette';
import Promise from 'bluebird';
import _ from 'underscore';
import $ from 'jquery';
import Growl from '../../utils/growl.js';

import i18n from '../../utils/i18n.js';
import Types from '../../utils/types.js';
import LoaderView from '../loaderView.js';
import CollectionManager from '../../common/collectionManager.js';
import AdminNavigationMenu from './adminNavigationMenu.js';
import RoleModels from '../../models/roles.js';
import PubFlow from '../../models/publicationFlow.js';


/**
 * The new permissions window
 * @class app.views.admin.adminIdeaPubFlow.AdminIdeaPubFlow
 */
export default class AdminIdeaPubFlow extends LoaderView.extend({
  template: "#tmpl-adminIdeaPubFlow",

  regions: {
    navigationMenuHolder: ".navigation-menu-holder",
    
  },
  ui: {
    nextFlow: '#next_flow',
    nextState: '.js-next-state',
    save: '.js_save'
  },
  events: {
    "change @ui.nextFlow": "changeNextFlow",
    "change @ui.nextState": "changeNextState",
    "click @ui.save": "save",
  }
}) {
  initialize() {
    this.setLoading(true);
    const that = this;
    const collectionManager = new CollectionManager();
    this.roleCollection = new RoleModels.roleCollection();
    this.permissionCollection = new RoleModels.permissionCollection();
    Promise.join(
        collectionManager.getAllPublicationFlowsPromise(),
        collectionManager.getDiscussionModelPromise(),
        collectionManager.getAllIdeasCollectionPromise(),
        collectionManager.getUserLanguagePreferencesPromise(),
    ).then(([pubFlowsCollection, discussionModel, ideasCollection, langPrefs])=>{
        this.pubFlowsCollection = pubFlowsCollection;
        this.discussion = discussionModel;
        this.ideasCollections = ideasCollection;
        this.langPrefs = langPrefs;
        this.computeCurrentIdeaCount();
        this.nextFlow = this.currentIdeaFlow;
        this.setLoading(false);
        this.render();
    });
  }

  computeCurrentIdeaCount() {
    const currentFlowName = this.discussion.get('idea_publication_flow_name');
    if (currentFlowName) {
      this.currentIdeaFlow = this.getFlowByLabel(currentFlowName);
      this.currentStates = this.currentIdeaFlow.get('states');
    } else {
      this.currentIdeaFlow = null;
      this.currentStates = new PubFlow.publicationStateCollection();
    }
    this.ideaCounts = this.ideasCollections.countBy((idea)=>idea.get('pub_state_name'));
    this.setNextFlow(this.currentIdeaFlow)
  }

  setNextFlow(flow) {
    this.nextFlow = flow;
    if (flow != this.currentIdeaFlow) {
      this.nextStates = this.nextFlow.get('states');
      const destLabels = this.nextStates.map((state)=>state.get('label'));
      this.nextStateMap = {}
      const defaultLabel = this.nextStates[0]; // arbitrary
      this.currentStates.each((state) => {
        const label = state.get('label');
        if (_.indexOf(destLabels, label) >= 0) {
          return this.nextStateMap[label] = label;
        } else {
          return this.nextStateMap[label] = defaultLabel;
        }
        return this.nextStateMap[label] = defaultLabel;
      });
    } else {
      // assume cannot delete flow
      const sourceLabels = this.currentStates.map((state)=>state.get('label'));
      this.nextStates = this.currentStates;
      this.nextStateMap = _.object(sourceLabels, sourceLabels);
      this.nextStateMap[null] = (sourceLabels.length) ? sourceLabels[0] : null;
    }
  }

  getFlowByLabel(label) {
    return this.pubFlowsCollection.find((flow) => flow.get('label')==label);
  }

  changeNextFlow(ev) {
    const flowLabel = ev.currentTarget.value;
    const flow = this.getFlowByLabel(flowLabel);
    if (flow != this.nextFlow) {
      this.setNextFlow(flow);
      this.render();
    }
  }

  changeNextState(ev) {
    const originStateLabelDecorated = ev.currentTarget.id;
    const stateLabel = ev.currentTarget.value;
    // pattern is "state-<label>-convert"
    const originStateLabel = originStateLabelDecorated.substring(
      6, originStateLabelDecorated.length-8);
    this.nextStateMap[originStateLabel] = stateLabel;
  }

  save(ev) {
    ev.preventDefault();
    $.ajax(Ctx.getApiV2DiscussionUrl("bulk_idea_pub_state_transition"), {
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify({flow: this.nextFlow.get('label'), changes: this.nextStateMap})
    }).then(function(data) {
      // do not try to reinterpret state...
      location.reload();
    }).catch(function(e) {
      Growl.showBottomGrowl(Growl.GrowlReason.ERROR, i18n.gettext("Your settings failed to update."));
    });
  }

  serializeData() {
    return {
      currentStates: this.currentStates,
      currentFlow: this.currentIdeaFlow,
      flowCollection: this.pubFlowsCollection,
      discussion: this.discussion,
      ideasCollections: this.ideasCollections,
      langPrefs: this.langPrefs,
      nextStates: this.nextStates,
      nextFlow: this.nextFlow,
      nextStateMap: this.nextStateMap,
      ideaCounts: this.ideaCounts,
      i18n,      
    }
  }

  onRender() {
    if (this.isLoading()) {
        return;
    }
    this.showChildView("navigationMenuHolder", this.getNavigationMenu());
  }

  getNavigationMenu() {
    return new AdminNavigationMenu.discussionAdminNavigationMenu(
      {selectedSection: "ideaPubFlow"});
  }
}
