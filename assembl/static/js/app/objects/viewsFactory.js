/**
 * 
 * @module app.objects.viewsFactory
 */

var _ = require('underscore');

var Types = require('../utils/types.js');
var AssemblPanel = require('../views/assemblPanel.js');
var AboutNavPanel = require('../views/navigation/about.js');
var ContextPanel = require('../views/contextPage.js');
var IdeaList = require('../views/ideaList.js');
var IdeaPanel = require('../views/ideaPanel.js');
var MessageList = require('../views/messageList.js');
var NavigationView = require('../views/navigation/navigation.js');
var SegmentList = require('../views/segmentList.js');
var SynthesisNavPanel = require('../views/navigation/synthesisInNavigation.js');
var SynthesisPanel = require('../views/synthesisPanel.js');
var CollectionManager = require('../common/collectionManager.js');
var ExternalVisualizationPanels = require('../views/externalVisualization.js');

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

module.exports = {byPanelSpec: panelViewByPanelSpec, typeByCode: typeByCode, decodeUrlData: decodeUrlData };
