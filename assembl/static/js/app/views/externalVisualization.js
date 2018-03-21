/**
 * 
 * @module app.views.externalVisualization
 */

import Marionette from 'backbone.marionette';

import i18n from '../utils/i18n.js';
import Ctx from '../common/context.js';
import PanelSpecTypes from '../utils/panelSpecTypes.js';
import BasePanel from './basePanel.js';

var externalVisualizationPanel = Marionette.View.extend({
  constructor: function externalVisualizationPanel() {
    Marionette.View.apply(this, arguments);
  },

  template: '#tmpl-externalViz',
  panelType: PanelSpecTypes.EXTERNAL_VISUALIZATION_CONTEXT,
  className: 'externalViz',
  gridSize: BasePanel.prototype.CONTEXT_PANEL_GRID_SIZE,
  minWidth: 450,
  hideHeader: true,
  getTitle: function() {
    return i18n.gettext('CI Dashboard'); // unused
  },
  ui: {
    external_visualization: 'iframe#external_visualization'
  },
  initialize: function(options) {
    this.listenTo(this, 'contextPage:render', this.render);
  },
  setUrl: function(url) {
    this.ui.external_visualization.attr('src', url);
  }
});

var dashboardVisualizationPanel = externalVisualizationPanel.extend({
  constructor: function dashboardVisualizationPanel() {
    externalVisualizationPanel.apply(this, arguments);
  },

  panelType: PanelSpecTypes.CI_DASHBOARD_CONTEXT,
  onRender: function(options) {
    if (!this.urlSetStarted) {
        this.urlSetStarted = true;
        var that = this;
        Ctx.deanonymizationCifInUrl(Ctx.getPreferences().ci_dashboard_url, function(url) {
            that.setUrl(url);
        });
    }
  }
});

export default {
    externalVisualizationPanel: externalVisualizationPanel,
    dashboardVisualizationPanel: dashboardVisualizationPanel
};
