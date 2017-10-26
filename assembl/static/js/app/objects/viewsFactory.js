/**
 * 
 * @module app.objects.viewsFactory
 */

import _ from 'underscore';

import Types from '../utils/types.js';
import AssemblPanel from '../views/assemblPanel.js';
import AboutNavPanel from '../views/navigation/about.js';
import ContextPanel from '../views/contextPage.js';
import IdeaList from '../views/ideaList.js';
import IdeaPanel from '../views/ideaPanel.js';
import MessageList from '../views/messageList.js';
import NavigationView from '../views/navigation/navigation.js';
import SegmentList from '../views/segmentList.js';
import SynthesisNavPanel from '../views/navigation/synthesisInNavigation.js';
import SynthesisPanel from '../views/synthesisPanel.js';
import CollectionManager from '../common/collectionManager.js';
import ExternalVisualizationPanels from '../views/externalVisualization.js';

/*
 * A registry of AssemblView subclasses implementing a panelSpec,
 * indexed by PanelSpec.id
 */
var panelTypeRegistry = {};

var typeByCode = {};
_.each([
    AboutNavPanel, ContextPanel, IdeaList, IdeaPanel, MessageList, NavigationView, SegmentList.SegmentListPanel, SynthesisNavPanel, SynthesisPanel, ExternalVisualizationPanels.externalVisualizationPanel, ExternalVisualizationPanels.dashboardVisualizationPanel
], function(panelClass) {

  var panelType = panelClass.prototype.panelType;

  //console.log(panelClass.prototype.panelType);
  panelTypeRegistry[panelType.id] = panelClass;
  typeByCode[panelType.code] = panelType.id;
});

//console.log("panelTypeRegistry:", panelTypeRegistry);

/**
 * Factory to create a view instance from the panelSpec passed as parameter
 *
 * @param <PanelSpecs.Model> panelSpecModel
 * @returns <AssemblPanel> AssemblPanel view
 */
function panelViewByPanelSpec(panelSpecModel) {
  var panelClass;
  var id;

  //console.log("panelViewByPanelSpec() called with ",panelSpecModel);
  try {
    id = panelSpecModel.getPanelSpecType().id;
    panelClass = panelTypeRegistry[id];

    if (!panelClass instanceof AssemblPanel) {
      throw new Error("panelClass isn't an instance of AssemblPanel");
    }

    //console.log("panelViewByPanelSpec() returning ",panelClass, "for",panelSpecModel)
    return panelClass;
  }
  catch (err) {
    //console.log('invalid spec:', panelSpecModel, "error was", err);
    throw new Error("invalidPanelSpecModel");
  }
}

function decodeUrlData(code, data) {
  if (code == 'i') {
    var ideasCollection = new CollectionManager().getAllIdeasCollectionPromise();
    return ideasCollection.then(function(ideas) {
        var idea = ideas.get("local:" + Types.IDEA + "/" + data);
        return ["currentIdea", idea];
      });
  }
}

export default {byPanelSpec: panelViewByPanelSpec, typeByCode: typeByCode, decodeUrlData: decodeUrlData };
