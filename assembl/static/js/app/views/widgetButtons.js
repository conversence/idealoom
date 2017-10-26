/**
 * 
 * @module app.views.widgetButtons
 */

import Backbone from 'backbone';

import Marionette from 'backbone.marionette';
import _ from 'underscore';
import i18n from '../utils/i18n.js';
import Moment from 'moment';
import Widget from '../models/widget.js';
import Ctx from '../common/context.js';
import Permissions from '../utils/permissions.js';


var WidgetButtonView = Marionette.View.extend({
  constructor: function WidgetButtonView() {
    Marionette.View.apply(this, arguments);
  },

  template: "#tmpl-widgetButton",
  initialize: function(options) {
    this.options = options;
  },
  ui: {
    button: ".btn",
  },
  events: {
    // "click @ui.button": "onButtonClick",
    'click .js_widget-vote': "onButtonClick",
    'click .js_widget-vote-result': "onResultButtonClick"
  },
  onButtonClick: function(evt) {
    console.log("WidgetButtonView::onButtonClick()");
    var context = this.options.context;
    var idea = this.options.idea;

    var openTargetInModalOnButtonClick = (this.model.getCssClasses(context, idea).indexOf("js_openTargetInModal") != -1);
    console.log("openTargetInModalOnButtonClick: ", openTargetInModalOnButtonClick);
    if ( openTargetInModalOnButtonClick !== false ) {
      var options = {
        footer: false
      };
      return Ctx.openTargetInModal(evt, null, options);
    }
    else {
      //Pass the event in case need to stop the default action of evt.
      this.model.trigger("buttonClick", evt);
    }
    return false;
  },
  onResultButtonClick: function(ev){
    console.log("triggering 'showResult' event on model", this.model);
    this.model.trigger('showResult', ev);
  },
  serializeData: function() {
    var endDate = this.model.get("end_date");
    
    return {
      link: this.model.getUrl(this.options.context, this.options.idea.getId()),
      button_text: this.model.getLinkText(this.options.context, this.options.idea),
      description: this.model.getDescriptionText(this.options.context, this.options.idea, this.options.translationData),
      classes: this.model.getCssClasses(this.options.context, this.options.idea),
      until_text: this.model.getDescriptionText(this.model.UNTIL_TEXT, this.options.idea, this.options.translationData),
      canSeeResults: Ctx.getCurrentUser().can(Permissions.ADMIN_DISCUSSION)
    };
  }
});

var WidgetButtonListView = Marionette.CollectionView.extend({
  constructor: function WidgetButtonListView() {
    Marionette.CollectionView.apply(this, arguments);
  },

  childView: WidgetButtonView,

  initialize: function(options) {
    this.childViewOptions = {
      context: options.context || options.collection.context,
      idea: options.idea || options.collection.idea,
      translationData: options.translationData,
    };
    if (this.childViewOptions.context === undefined) {
      console.error("Undefined context in WidgetButtonListView");
    }
  }
});


export default {
  WidgetButtonView: WidgetButtonView,
  WidgetButtonListView: WidgetButtonListView
};
