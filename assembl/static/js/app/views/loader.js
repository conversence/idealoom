/**
 * 
 * @module app.views.loader
 */

var Marionette = require('backbone.marionette');

var _ = require('underscore');
var Assembl = require('../app.js');
var Ctx = require('../common/context.js');

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

module.exports = LoaderView;
