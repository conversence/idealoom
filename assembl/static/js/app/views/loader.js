/**
 * 
 * @module app.views.loader
 */

import Marionette from 'backbone.marionette';

import _ from 'underscore';
import IdeaLoom from '../app.js';
import Ctx from '../common/context.js';

var LoaderView = Marionette.View.extend({
  constructor: function LoaderView() {
    Marionette.View.apply(this, arguments);
  },

  template: '#tmpl-loader',
    
  onRender: function() {
    // Get rid of that pesky wrapping-div.
    // Assumes 1 child element present in template.
    this.$el = this.$el.children();

    // Unwrap the element to prevent infinitely 
    // nesting elements during re-render.
    this.$el.unwrap();
    this.setElement(this.$el);
  }
});

export default LoaderView;
