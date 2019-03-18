/**
 * 
 * @module app.views.widgetLinks
 */

import Backbone from 'backbone';

import Marionette from 'backbone.marionette';
import _ from 'underscore';
import $ from 'jquery';
import Widget from '../models/widget.js';


class WidgetLinkView extends Marionette.View.extend({
  template: "#tmpl-widgetLink",
  tagName: 'li',

  ui: {
    anchor: ".js_widgetLinkAnchor"
  },

  events: {
    "click @ui.anchor": "onAnchorClick"
  }
}) {
  initialize(options) {
    this.options = options;
  }

  onAnchorClick(evt) {
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
  }

  serializeData() {
    return {
      link: this.model.getUrl(this.options.context, this.options.idea.getId()),
      text: this.model.getLinkText(this.options.context, this.options.idea)
    };
  }
}

class WidgetLinkListView extends Marionette.CollectionView.extend({
  childView: WidgetLinkView
}) {
  initialize(options) {
    this.childViewOptions = {
      context: options.context || options.collection.context,
      idea: options.idea || options.collection.idea
    };
    if (this.childViewOptions.context === undefined) {
      console.error("Undefined context in WidgetLinkListView");
    }
  }
}


export default {
  WidgetLinkView: WidgetLinkView,
  WidgetLinkListView: WidgetLinkListView
};
