'use strict';

var Backbone = require('backbone'),
    Marionette = require('backbone.marionette'),
    _ = require('underscore'),
    $ = require('jquery'),
    panels = require('./panels.js');

var TestPanel = panels.BasePanel.extend({
  constructor: function TestPanel() {
    panels.BasePanel.apply(this, arguments);
    this.model = new Backbone.Model();
    if (this.model.get('subpanels') === undefined) {
      this.model.set('subpanels', []);
    }
  },

  ui: {
    dropdown: '#dropdown',
  },

  events: {
    'change @ui.dropdown': 'selectChanged',
  },

  selectChanged: function(event) {
    this.model.set('subpanels', _.filter(event.target.value.split('_'), function(x) {
      return x.length > 0;
    }));
    this.wrapper.panelGroup.changeSelection({});
  },

  getAllowedPanelNames: function() {
      return this.model.get('subpanels');
  },

  getAutoactivatedPanelNames: function() {
      return this.model.get('subpanels');
  },

  serializeData: function() {
    return {
      panelN: this.wrapper.indexInLevel(),
      levelN: this.wrapper.panelLevel.indexInColumn(),
      columnN: this.wrapper.panelColumn.indexInColumns(),
      groupN: this.wrapper.panelGroup.indexInManager(),
    };
  },

  name: 'test',
  className: 'panel test-panel',
  template: _.template(
    'G<%= groupN %>C<%= columnN %>L<%= levelN %>P<%= panelN %> '+
    'choose: <select id="dropdown" name="dropdown">'+
    '<option id="" selected></option>'+
    '<option id="test">test</option>'+
    '<option id="test2">test2</option>'+
    '<option id="test21">test2_test</option>'+
    '</select>'),
});

var Test2Panel = TestPanel.extend({
  constructor: function Test2Panel() {
    TestPanel.apply(this, arguments);
  },
  name: 'test2',
  className: 'panel test2-panel',
  getMinWidth: function() {
    return 300;
  },
});

panels.PanelManager.prototype.registerPanelClass(TestPanel);
panels.PanelManager.prototype.registerPanelClass(Test2Panel);


var App =  Marionette.Application.extend({
  region: '#testapp',

  onStart: function() {
    this.panelManager = new panels.PanelManager({
      rootName: 'test',
    });
    this.showView(this.panelManager);
    this.panelManager.children.each(function(group) {
      group.changeSelection({});
    });
    $(window).on("resize", _.bind(this.windowResized, this));
  },
  windowResized: function() {
    this.panelManager.resize(window.innerWidth);
  },
});

document.addEventListener('DOMContentLoaded', () => {
  var app = new App();
  window.app = app;
  app.start();
});
