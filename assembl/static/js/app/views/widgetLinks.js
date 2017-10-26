/**
 * 
 * @module app.views.widgetLinks
 */

import Backbone from 'backbone';

import Marionette from 'backbone.marionette';
import _ from 'underscore';
import $ from 'jquery';
import Widget from '../models/widget.js';


var WidgetLinkView = Marionette.View.extend({
  constructor: function WidgetLinkView() {
    Marionette.View.apply(this, arguments);
  },

  template: "#tmpl-widgetLink",
  tagName: 'li',
  initialize: function(options) {
    this.options = options;
  },
  ui: {
    anchor: ".js_widgetLinkAnchor"
  },
  events: {
    "click @ui.anchor": "onAnchorClick"
  },
  onAnchorClick: function(evt) {
    var that = this;

    var onDestroyCallback = function() {
      setTimeout(function() {
        that.clearWidgetDataAssociatedToIdea();
        that.render();
      }, 0);
    };

    var options = {
      footer: false
    };

    if (evt && evt.currentTarget && $(evt.currentTarget).hasClass(
        "js_clearWidgetDataAssociatedToIdea")) {
      return Ctx.openTargetInModal(evt, onDestroyCallback, options);
    } else {
      return Ctx.openTargetInModal(evt, null, options);
    }
  },
  serializeData: function() {
    return {
      link: this.model.getUrl(this.options.context, this.options.idea.getId()),
      text: this.model.getLinkText(this.options.context, this.options.idea)
    };
  }
});

var WidgetLinkListView = Marionette.CollectionView.extend({
  constructor: function WidgetLinkListView() {
    Marionette.CollectionView.apply(this, arguments);
  },

  childView: WidgetLinkView,

  initialize: function(options) {
    this.childViewOptions = {
      context: options.context || options.collection.context,
      idea: options.idea || options.collection.idea
    };
    if (this.childViewOptions.context === undefined) {
      console.error("Undefined context in WidgetLinkListView");
    }
  }
});


export default {
  WidgetLinkView: WidgetLinkView,
  WidgetLinkListView: WidgetLinkListView
};
