import $ from 'jquery';
import _ from 'underscore';
import Backbone from 'backbone';
import Marionette from 'backbone.marionette';
import { BasePanel, PanelManager } from './backbonePanels.js';

class TestPanel extends BasePanel.extend({
  ui: {
    dropdown: '#dropdown',
  },

  events: {
    'change @ui.dropdown': 'selectChanged',
  },
  name: 'test',
  className: 'panel test-panel',
  template: _.template(
    'G<%= groupN %>C<%= columnN %>L<%= levelN %>P<%= panelN %> ' +
    'choose: <select id="dropdown" name="dropdown">' +
    '<option id="" selected></option>' +
    '<option id="test">test</option>' +
    '<option id="test2">test2</option>' +
    '<option id="test21">test2_test</option>' +
    '</select>'),
}) {
  constructor() {
    super();
    this.model = new Backbone.Model();
    if (this.model.get('subpanels') === undefined) {
      this.model.set('subpanels', []);
    }
  }

  selectChanged(event) {
    this.model.set('subpanels', _.filter(event.target.value.split('_'), function(x) {
      return x.length > 0;
    }));
    this.wrapper.panelGroup.changeSelection({});
  }

  getAllowedPanelNames() {
      return this.model.get('subpanels');
  }

  getAutoactivatedPanelNames() {
      return this.model.get('subpanels');
  }

  serializeData() {
    return {
      panelN: this.wrapper.indexInLevel(),
      levelN: this.wrapper.panelLevel.indexInColumn(),
      columnN: this.wrapper.panelColumn.indexInColumns(),
      groupN: this.wrapper.panelGroup.indexInManager(),
    };
  }
}

class Test2Panel extends TestPanel.extend({
  name: 'test2',
  className: 'panel test2-panel',
}) {
  getMinWidth() {
    return 300;
  }
}

PanelManager.prototype.registerPanelClass(TestPanel);
PanelManager.prototype.registerPanelClass(Test2Panel);


class App extends Marionette.Application.extend({
  region: '#testapp',
}) {
  onStart() {
    this.panelManager = new PanelManager({
      rootName: 'test',
    });
    this.showView(this.panelManager);
    this.panelManager.children.each((group) => group.changeSelection({}));
    $(window).on("resize", _.bind(this.windowResized, this));
  }
  windowResized() {
    this.panelManager.resize(window.innerWidth);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  var app = new App();
  window.app = app;
  app.start();
});
