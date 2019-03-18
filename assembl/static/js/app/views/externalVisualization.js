/**
 * 
 * @module app.views.externalVisualization
 */

import Marionette from 'backbone.marionette';

import i18n from '../utils/i18n.js';
import Ctx from '../common/context.js';
import PanelSpecTypes from '../utils/panelSpecTypes.js';
import BasePanel from './basePanel.js';

class externalVisualizationPanel extends Marionette.View.extend({
  template: '#tmpl-externalViz',
  panelType: PanelSpecTypes.EXTERNAL_VISUALIZATION_CONTEXT,
  className: 'externalViz',
  gridSize: BasePanel.prototype.CONTEXT_PANEL_GRID_SIZE,
  minWidth: 450,
  hideHeader: true,

  ui: {
    external_visualization: 'iframe#external_visualization'
  }
}) {
  getTitle() {
    return i18n.gettext('CI Dashboard'); // unused
  }

  initialize(options) {
    this.listenTo(this, 'contextPage:render', this.render);
  }

  setUrl(url) {
    this.ui.external_visualization.attr('src', url);
  }
}

class dashboardVisualizationPanel extends externalVisualizationPanel.extend({
  panelType: PanelSpecTypes.CI_DASHBOARD_CONTEXT
}) {
  onRender(options) {
    if (!this.urlSetStarted) {
        this.urlSetStarted = true;
        var that = this;
        Ctx.deanonymizationCifInUrl(Ctx.getPreferences().ci_dashboard_url, function(url) {
            that.setUrl(url);
        });
    }
  }
}

export default {
    externalVisualizationPanel: externalVisualizationPanel,
    dashboardVisualizationPanel: dashboardVisualizationPanel
};
