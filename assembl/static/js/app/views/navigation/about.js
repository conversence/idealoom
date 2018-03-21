/**
 * 
 * @module app.views.navigation.about
 */

import IdeaLoom from '../../app.js';

import BasePanel from '../basePanel.js';
import PanelSpecTypes from '../../utils/panelSpecTypes.js';
import Analytics from '../../internal_modules/analytics/dispatcher.js';

var AboutNavPanel = BasePanel.extend({
  constructor: function AboutNavPanel() {
    BasePanel.apply(this, arguments);
  },

  template: '#tmpl-about',
  panelType: PanelSpecTypes.NAVIGATION_PANEL_ABOUT_SECTION,
  className: 'aboutNavPanel',
  ui: {
    debate: '.js_go-to-debate'
  },
  events: {
    'click @ui.debate': 'goToDebate',
    'click .js_test_stuff_analytics': 'testAnalytics',
    'click .js_trackInteractionExample': 'testAnalytics2'
  },
  initialize: function(options) {
      BasePanel.prototype.initialize.apply(this, arguments);
    },
  goToDebate: function() {
    IdeaLoom.other_vent.trigger("DEPRECATEDnavigation:selected", "debate");
  },
  testAnalytics: function(e){
    e.stopPropagation();
    e.preventDefault();
    var a = Analytics.getInstance();
    a.trackImpression("DummyContentName", "DummyContentPiece", "http://dummyurl.fc.uk");
  },
  testAnalytics2: function(e){
    e.stopPropagation();
    e.preventDefault();
    var a = Analytics.getInstance();
    a.trackContentInteraction("DummyInteraction", "DummyContentName", "DummyContentPiece", "http://dummyurl.fc.uk");
  }
});

export default AboutNavPanel;
