/**
 * 
 * @module app.views.navigation.linkListView
 */

import _ from 'underscore';

import $ from 'jquery';
import Promise from 'bluebird';
import Marionette from 'backbone.marionette';
import Ctx from '../../common/context.js';
import Permissions from '../../utils/permissions.js';

var SimpleLinkView = Marionette.View.extend({
  constructor: function SimpleLinkView() {
    Marionette.View.apply(this, arguments);
  },

  template: '#tmpl-simpleLink',
  initialize: function(options) {
    this.groupContent = options.groupContent;
  },
  ui: {
    'links': '.externalvizlink'
  },
  events: {
    'click @ui.links': 'linkClicked'
  },
  linkClicked: function(a) {
    var content = this.groupContent;
    Ctx.deanonymizationCifInUrl(this.model.get('url'), function(url) {
        content.NavigationResetVisualizationState(url);
    });
  }
});

var LinkListView = Marionette.CollectionView.extend({
  constructor: function LinkListView() {
    Marionette.CollectionView.apply(this, arguments);
  },

  childView: SimpleLinkView,
  initialize: function(options) {
    this.collection = options.collection;
    this.groupContent = options.groupContent;
    this.childViewOptions = {
      'groupContent': options.groupContent
    };
  }
});

export default LinkListView;
