// Note on animation: https://github.com/marionettejs/backbone.marionette/issues/320
// https://github.com/marcinkrysiak1979/marionette.showAnimated/blob/master/backbone.marionette.showAnimated.js

/**
 *
 * @module app.views.panels
 */

import _ from 'underscore';
import Backbone from 'backbone';
import Marionette from 'backbone.marionette';


function assert(condition, msg) {
  if (!condition) {
    console.error(msg || "error");
    debugger;
  }
}

/**
 * @class app.views.panels.ViewModel
 */
class ViewModel extends Backbone.Model {
}

/**
 * @class app.views.panels.ViewModelCollection
 */
class ViewModelCollection extends Backbone.Collection.extend({
  model: ViewModel,
}) {
}

/**
 * @class app.views.panels.PanelModel
 */
class PanelModel extends ViewModel.extend({
  defaults: {
    panelName: '',
    minimized: false,
  },
}) {
}


/**
 * @class app.views.panels.PanelModelCollection
 */
class PanelModelCollection extends ViewModelCollection.extend({
  model: PanelModel,
}) {
}


/**
 * @class app.views.panels.PanelLevelModel
 */
class PanelLevelModel extends ViewModel {
  defaults() {
    return {
      collection: new PanelModelCollection(),
    };
  }
}

/**
 * @class app.views.panels.PanelLevelModelCollection
 */
class PanelLevelModelCollection extends ViewModelCollection.extend(
  { model: PanelLevelModel, }) {
}


/**
 * @class app.views.panels.PanelColumnModel
 */
class PanelColumnModel extends ViewModel {
  defaults() {
    return {
      collection: new PanelLevelModelCollection(),
    };
  }
}


/**
 * @class app.views.panels.PanelColumnModelCollection
 */
class PanelColumnModelCollection extends ViewModelCollection.extend({
  model: PanelColumnModel,
}) {
}

/**
 * @class app.views.panels.PanelGroupModel
 */
class PanelGroupModel extends ViewModel {
  defaults() {
    return {
      collection: new PanelColumnModelCollection(),
    };
  }
}

/**
 * @class app.views.panels.PanelGroupModelCollection
 */
class PanelGroupModelCollection extends ViewModelCollection.extend({
  model: PanelGroupModel,
}) {
}


/**
 * @class app.views.panels.PanelManagerModel
 */
class PanelManagerModel extends ViewModel {
  defaults() {
    return {
      collection: new PanelGroupModelCollection(),
    };
  }
}

/**
 * @class app.views.panels.PanelManagerModelCollection
 */
class PanelManagerModelCollection extends ViewModelCollection.extend({
  model: PanelManagerModel,
}) {
}

/**
 * An abstract class every panel should eventually extend
 * @class app.views.views.BasePanel
 */
export class BasePanel extends Marionette.View.extend({
  name: '', }) {

  registerClass() {
    PanelManager.prototype.registerPanelClass(this);
  }

  changeSelection(selectionChanges) {
    //
  }

  getAllowedPanelNames() {
    return [];  // String[]
  }

  getAutoactivatedPanelNames() {
      return [];  // String[]
  }

  getMinWidth() {
      return 200;
  }

  getMaxWidth() {
      return 1500;
  }

  getMinHeight() {
      return 20;
  }

  setMinimize(minimize) {
    
  }
}


/**
 * An abstract class every panel should eventually extend
 * @class app.views.views.PanelWrapper
 */
class PanelWrapper extends Marionette.View.extend({
  ui: {
    panel: '.panelc',
    header: '.panelw-header',
    minButton: '.js_min',
  },
  regions: {
    panelR: '@ui.panel',
    header: '@ui.header',
  },
  events: {
    'click @ui.minButton': 'toggleMinimize',
  },
  className: 'panel-w',
  template: _.template("<div class='panelw-header'><%= panelName %><button class='js_min'><%= minSymbol %></button></div><div class='panelc'></div>"),
}) {

  initialize(options) {
    this.minimized = !!this.model.get('minimized');
    this.panelManager = options.panelManager;
    this.panelGroup = options.panelGroup;
    this.panelLevel = options.panelLevel;
    this.panelColumn = options.panelColumn;
    this.panelColumns = options.panelColumns;
  }

  serializeData() {
    return {
      panelName: this.model.get('panelName'),
      minSymbol: (this.minimized) ? '+' : '-',
    };
  }

  onRender(options) {
    const panelName = this.model.get('panelName');
    const panel = PanelManager.prototype.createPanelByName(panelName);
    if (panel) {
      panel.wrapper = this;
      this.panel = panel;
      this.showChildView('panelR', panel);
    } else {
      this.ui.panel.text("Cannot find "+panelName)
    }
  }

  onAttach() {
    if (this.minimized) {
      this.$el.addClass('minimized');
    }
  }

  toggleMinimize() {
    this.setMinimize(!this.minimized);
    this.$el.find('.js_min').text((this.minimized) ? '+' : '-');
  }

  setMinimize(minimized) {
    if (minimized !== this.minimized) {
      // console.log("setting min of panel G"+this.panelGroup.indexInManager()
      // +"C"+this.panelColumn.indexInColumns()+"L"+this.panelLevel.indexInColumn()
      // +"P"+this.indexInLevel()+" to "+minimized);
      if (minimized) {
        this.$el.addClass('minimized');
      } else {
        this.$el.removeClass('minimized');
      }
      this.minimized = minimized;
      this.model.set('minimized', minimized);
      this.panel.setMinimize(minimized);
      this.panelLevel.updateMinimize(this);
      this.panelManager.updateMinimize(this);
      this.panelManager.resetPercent();
    }
  }

  indexInLevel() {
    return this.panelLevel.panelCollection.collection.indexOf(this.model);
  }

  getAllowedPanelNames() {
    return this.panel.getAllowedPanelNames();
  }

  getAutoactivatedPanelNames() {
    return this.panel.getAutoactivatedPanelNames();
  }

  getMinWidth() {
    return this.panel.getMinWidth();
  }

  getMaxWidth() {
    return this.panel.getMaxWidth();
  }

  getMinHeight() {
    return this.panel.getMinHeight() + 20;
  }

  changeSelection(selectionChanges) {
    return this.panel.changeSelection(selectionChanges);
  }
}


/**
 * @class app.views.views.PanelCollection
 */
class PanelCollection extends Marionette.CollectionView.extend({
    // Is it a Marionette object or an abstraction?
    // Clearly the former in the case of a multipanel level, at least.
  singlePanel: true,
  className: 'panel-collection',
  childView: PanelWrapper,
}) {
  initialize(options) {
    this.collection = this.model.get('collection');
    this.panelManager = options.panelManager;
    this.panelGroup = options.panelGroup;
    this.panelColumn = options.panelColumn;
    this.panelColumns = options.panelColumns;
    this.panelLevel = options.panelLevel;
  }

  getPanelWrappers() {
    return this.children;
  }


  childViewOptions() {
    return {
      panelManager: this.panelManager,
      panelGroup: this.panelGroup,
      panelColumn: this.panelColumn,
      panelColumns: this.panelColumns,
      panelLevel: this.panelLevel,
    };
  }

  _addPanel(panelName, allowedPanelNames, minimized) {
    // check for duplicates? Do we allow them?
    const pos = allowedPanelNames.indexOf(panelName);
    if (pos < -1) {
      return;
    }
    const model = new PanelModel({
      panelName,
      minimized,
    });
    // This is kinda sorted. I do not do a full sort, because I do not want
    // to reorder already-active panels.
    const nextModel = this.collection.find((model, index) => pos < allowedPanelNames.indexOf(model.get('panelName')));
    if (nextModel === undefined) {
      this.collection.push(model);
    } else {
      this.collection.add(model, { at: this.collection.indexOf(nextModel) });
    }
    this.panelManager.updateMinimize();
  }

  activateOnePanel(panelName) {
    const models = this.collection.where({panelName});
    if (models.length == 0) {
      models.push(new PanelModel({
        panelName,
        minimized: false,
      }));
    }
    this.collection.reset(models);
  }

  _removePanel(panelOrName) {
    let model;
    if (panelOrName instanceof PanelWrapper) {
      model = this.collection.find((model) => model === panelOrName.model);
    } else if (panelOrName instanceof BasePanel) {
      model = this.collection.find((model) => model === panelOrName.wrapper.model);
    } else {
      model = this.collection.find((model) => model.get('panelName') === panelOrName);
    }
    if (model != null) {
      this.collection.remove(model);
      this.panelManager.updateMinimize();
    }
    // panel.terminate() // or whatever needed to avoid leaks
  }

  changeSelection(selectionChanges) {
    this.getPanelWrappers().each((panel) => {
      panel.changeSelection(selectionChanges);
    });
  }
}


class PanelSelectorModel extends Backbone.Model {
}


class PanelSelectorModelCollection extends Backbone.Collection.extend({
  model: PanelSelectorModel,
  defaults: {
    name: null,
    active: false,
  },
}) {
  activateOne(name) {
    this.each((model) => {
      model.set('active', model.get('name') == name);
    });
  }
}


class PanelSelectorView extends Marionette.View.extend({
  template: _.template("<button class='js_toggle_panel <%= active_class %>' <%= disabled %> ><%= name %></button><% if (allow_dup) { %><button class='js_add_panel'>+</button><% } %>"),
  className: 'panel-selector',
  ui: {
    toggle_panel: '.js_toggle_panel',
    add_panel: '.js_add_panel',
  },
  events: {
    'click @ui.toggle_panel': 'togglePanel',
    'click @ui.add_panel': 'addPanel',
  },
}) {
  initialize(options) {
    this.allow_multiple = options.allow_multiple;
    this.panelLevel = options.panelLevel;
    this.collView = options.collView;
  }
  serializeData() {
    const active = this.model.get('active'),
          disabled = active && this.panelLevel.getPanelWrappers().length == 1;
    return {
      name: this.model.get('name'),
      active_class: (active)?'button_down':'',
      disabled: (disabled)?'disabled':'',
      allow_dup: this.allow_multiple && !active,
    };
  }
  togglePanel() {
    const name = this.model.get('name');
    if (this.model.get('active')) {
      this.panelLevel.removePanel(name);
      this.model.set('active', false);
    } else {
      this.panelLevel.activateOnePanel(name);
      this.model.collection.activateOne(name);
    }
    this.collView.render();
  }
  addPanel() {
    this.model.set('active', true);
    this.panelLevel.addPanel(this.model.get('name'));
    this.collView.render();
  }
}


class PanelSelectorCollectionView extends Marionette.CollectionView.extend({
  childView: PanelSelectorView,
  className: 'panel-selector-collection',
}) {
  childViewOptions() {
    return {
      panelLevel: this.panelLevel,
      allow_multiple: this.allow_multiple,
      collView: this,
    };
  }
  initialize(options) {
    this.allow_multiple = options.allow_multiple;
    this.panelLevel = options.panelLevel;
  }
}

/**
 * @class app.views.views.PanelLevel
 */
export class PanelLevel extends Marionette.View.extend({
  template: _.template("<div class='level-header'></div><div class='panels'></div>"),
  singlePanel: true,
  className: 'panel-level',
  ui: {
    panels: '.panels',
    header: '.level-header',
  },
  regions: {
    panels: '@ui.panels',
    header: '@ui.header',
  },
}) {
  initialize(options) {
    this.minimized = !!this.model.get('minimized');
    this.panelManager = options.panelManager;
    this.panelGroup = options.panelGroup;
    this.panelColumn = options.panelColumn;
    this.panelColumns = options.panelColumns;
    options.panelLevel = this;
    this.panelCollection = new PanelCollection(options);
    this.singlePanel = options.singlePanel;
    this.allowedPanelNames = [];
    this.panelSelectorModels = new PanelSelectorModelCollection();
    this.panelSelectorsView = new PanelSelectorCollectionView({
      collection: this.panelSelectorModels,
      panelLevel: this,
      allow_multiple: true,
    });
  }

  serializeData() {
    return {
      levelN: this.indexInColumn(),
      columnN: this.panelColumn.indexInColumns(),
      groupN: this.panelGroup.indexInManager(),
    };
  }

  onRender() {
    this.renderHeader();
    this.showChildView('panels', this.panelCollection);
  }

  renderHeader() {
    const child = this.getChildView('header');
    if (this.panelSelectorModels.length > 1) {
      if (child) {
        child.render();
      } else {
        this.showChildView('header', this.panelSelectorsView);
      }
    } else {
      if (child) {
        this.detachChildView('header');
      }
    }
  }

  onAttach() {
    if (this.minimized) {
      this.$el.addClass('minimized');
    }
  }
  getPanelWrappers() {
    return this.panelCollection.getPanelWrappers();
  }

  indexInColumn() {
    // coming soon
    return this.panelColumn.collection.indexOf(this.model);
  }

  addPanel(panelName) {
    this.panelCollection._addPanel(panelName, this.allowedPanelNames);
    const multiPanel = (this.panelCollection.collection.length > 1);
    if (multiPanel && this.singlePanel) {
      console.log('error');
      return;
    }
  }
  activateOnePanel(panelName) {
    this.panelCollection.activateOnePanel(panelName);
  }
  getMinWidth() {
    const panels = this.getPanelWrappers();
    let width = 0;
    let previousIsMinimized = false;
    panels.each((panel) => {
      const panelWidth = panel.getMinWidth();
      if (previousIsMinimized) {
        width = Math.max(width, panelWidth);
      } else {
        width += panelWidth;
      }
      previousIsMinimized = panel.minimized;
    });
    return width;
  }
  getMaxWidth() {
    const panels = this.getPanelWrappers();
    let width = 0;
    let previousIsMinimized = false;
    panels.each((panel) => {
      const panelWidth = panel.getMaxWidth();
      if (previousIsMinimized) {
        width = Math.min(width, panelWidth);
      } else {
        width += panelWidth;
      }
      previousIsMinimized = panel.minimized;
    });
    return width;
  }
  getMinHeight() {
    const panels = this.getPanelWrappers();
    let height = 0;
    panels.each((wrapper) => {
      height += wrapper.getMinHeight();
    });
    return height;
  }
  updateMinimize(panel) {
    const minimized = this.getPanelWrappers().all((p) => p.minimized);
    if (minimized !== this.minimized) {
      // console.log("setting min of level G"+this.panelGroup.indexInManager()
      // +"C"+this.panelColumn.indexInColumns()+"L"+this.indexInColumn()+" to "+minimized);
      if (minimized) {
        this.$el.addClass('minimized');
      } else {
        this.$el.removeClass('minimized');
      }
      this.minimized = minimized;
      this.model.set('minimized', minimized);
      this.panelColumns.updateMinimize(this);
      this.panelGroup.updateMinimize(panel);
    }
  }

  nextPanelToMinimize() {
    return this.getPanelWrappers().find((panel) => !panel.minimized);
  }

  nextPanelToUnminimize() {
    let panels = this.getPanelWrappers();
    // reverse
    panels = panels.last(panels.length);
    return _.find(panels, (panel) => panel.minimized);
  }

  removePanel(panelOrName) {
    this.panelCollection._removePanel(panelOrName);
  }

  changeSelection(selectionChanges) {
    this.panelCollection.changeSelection(selectionChanges);
  }

  resetWithNames(allowedPanelNames, autoactivatedPanelNames) {
    let panelsChange = false;
    let selChange = false;
    let panels = this.getPanelWrappers();
    let numActive = panels.length;
    panels.each((panel) => {
      if (!_.contains(allowedPanelNames, panel.panel.name)) {
        this.removePanel(panel);
        const sel = this.panelSelectorModels.find((sel) => sel.get('name') == panel.panel.name);
        if (sel) {
          this.panelSelectorModels.remove(sel);
          selChange = true;
        }
        numActive -= 1;
        panelsChange = true;
      }
    });
    // assumption: Only autoactivate if nothing active.
    if (autoactivatedPanelNames.length && !numActive) {
      this.addPanel(autoactivatedPanelNames[0]);
      numActive = 1;
      panelsChange = true;
    }
    this.allowedPanelNames = allowedPanelNames;
    panels = this.getPanelWrappers();
    const activeNames = panels.map((panel) => panel.model.get('panelName'));
    const newSelectors = _.map(allowedPanelNames, (name) => new PanelSelectorModel({
      name,
      active: _.contains(activeNames, name),
    }));
    this.panelSelectorModels.reset(newSelectors);
    this.renderHeader();
    return panelsChange;
  }
}


/**
 * PanelColumn aka PanelLevelCollection
 * @class app.views.views.PanelColumn
 */
class PanelColumn extends Marionette.CollectionView.extend({
  className: 'panel-column',
  childView: PanelLevel,
}) {

  initialize(options) {
    this.rootName = options.rootName;
    this.panelManager = options.panelManager;
    this.panelGroup = options.panelGroup;
    this.panelColumns = options.panelColumns;
    this.collection = this.model.get('collection');
  }
  indexInColumns() {
    return this.panelColumns.collection.indexOf(this.model);
  }
  getLevels() {
    return this.children;
  }
  getSelection() {
    return this.panelGroup.getSelection();
  }
  pushLevel() {
    this.collection.add(new PanelLevelModel());
  }
  childViewOptions(view, index) {
    return {
      panelManager: this.panelManager,
      panelGroup: this.panelGroup,
      panelColumns: this.panelColumns,
      panelColumn: this,
    };
  }
  removeLastLevel() {
    this.collection.pop();
  }
  getLastLevel() {
    const lastModel = this.collection.last();
    if (lastModel) {
      return this.children.findByModel(lastModel);
    }
  }
  getMinWidth() {
    const levels = this.getLevels();
    let width = 0;
    let previousIsMinimized = false;
    levels.each((level) => {
      const levelWidth = level.getMinWidth();
      if (previousIsMinimized) {
        width = Math.min(width, levelWidth);
      } else {
        width += levelWidth;
      }
      previousIsMinimized = level.minimized;
    });
    return width;
  }
  getMaxWidth(panel) {
    const levels = this.getLevels();
    let width = 0;
    let previousIsMinimized = false;
    levels.each((level) => {
      const levelWidth = level.getMaxWidth();
      if (previousIsMinimized) {
        width = Math.min(width, levelWidth);
      } else {
        width += levelWidth;
      }
      previousIsMinimized = level.minimized;
    });
    return width;
  }
  getMinimizedHeight() {
    const levels = this.getLevels();
    let height = 0;
    levels.each((level) => {
      if (level.minimized) {
        height += level.getMinHeight();
      }
    });
    return height;
  }
  nextLevel(level) {
    const i = this.collection.indexOf(level.model);
    if (i < this.children.length - 1) {
      return this.children.findByModel(this.collection.at(i+1));
    }
  }
  resetPercent(minWidth) {
    const myMinWidth = this.getMinWidth();
    this.$el.css("width", (100.0*myMinWidth/minWidth)+"%");
  }
}


/**
 * @class app.views.views.PanelColumnCollection
 */
class PanelColumnCollection extends Marionette.CollectionView.extend({
  className: 'panel-column-collection',
  childView: PanelColumn,
}) {
  initialize(options) {
    this.rootName = options.rootName;
    this.panelManager = options.panelManager;
    this.panelGroup = options.panelGroup;
    this.rootName = options.rootName;
    this.collection = this.model.get('collection');
  }
  getColumns() {
    return this.children;
  }
  getLevels() {
    const levels = [];
    // costly for no good reason.
    this.collection.each((columnModel) => {
      const column = this.children.findByModel(columnModel);
      column.collection.each((levelModel) => {
        const level = column.children.findByModel(levelModel);
        levels.push(level);
      });
    });
    return levels;
  }
  getLevelByIndex(i) {
    const column = this.children.find((column) => {
      if (i >= column.children.length) {
        i -= column.children.length;
        return false;
      } else {
        return true;
      }
    });
    if (column) {
      return column.children.findByModel(column.collection.at(i));
    }
  }
  nextColumn(column) {
    const i = this.collection.indexOf(column.model);
    if (i < this.children.length - 1) {
      return this.children.findByModel(this.collection.at(i+1));
    }
  }
  previousColumn(column) {
    const i = this.collection.indexOf(column.model);
    if (i > 0) {
      return this.children.findByModel(this.collection.at(i-1));
    }
  }
  nextLevel(level) {
    let other = level.panelColumn.nextLevel(level);
    if (other) {
      return other;
    }
    other = this.nextColumn(level.panelColumn);
    if (other) {
      return other.children[0];
    }
  }
  countLevels() {
    let numLevels = 0;
    this.children.each((column) => {
      numLevels += column.collection.length;
    });
    return numLevels;
  }
  getSelection() {
    return this.panelGroup.getSelection();
  }
  childViewOptions(view, index) {
    return {
      panelManager: this.panelManager,
      panelGroup: this.panelGroup,
      rootName: this.rootName,
      panelColumns: this,
    };
  }
  pushColumn() {
    this.collection.add(new PanelColumnModel());
  }
  pushLevel() {
    this.pushColumn();
    this.children.last().pushLevel();
  }
  removeLastLevel() {
    assert(this.collection.length > 0, "no columns?");
    const columnModel = this.collection.last(),
          view = this.children.findByModel(columnModel);
    assert(view.collection.length > 0, "no level in column?");
    view.removeLastLevel();
    if (view.getLevels().length == 0) {
      this.collection.pop();
    }
  }
  changeSelection(selectionChanges) {
    let numLevels = this.countLevels(),
        allowedPanelNames = [this.rootName],
        autoactivatedPanelNames = allowedPanelNames,
        pos = 0,
        level,
        change = false,
        autoactivate = true;
    while (autoactivate) {
      while (pos >= numLevels) {
        this.pushLevel();
        numLevels++;
        change = true;
      }
      level = this.getLevelByIndex(pos++);
      change = level.resetWithNames(allowedPanelNames, autoactivatedPanelNames) || change;
      allowedPanelNames = [];
      autoactivate = false;
      autoactivatedPanelNames = [];
      level.getPanelWrappers().each((panel) => {
        panel.changeSelection(selectionChanges);
        allowedPanelNames = allowedPanelNames.concat(panel.getAllowedPanelNames());
        autoactivatedPanelNames = autoactivatedPanelNames.concat(panel.getAutoactivatedPanelNames());
      });
      if (allowedPanelNames.length === 0) {
        while (numLevels > pos) {
          this.removeLastLevel();
          numLevels -= 1;
          change = true;
        }
        break;
      }
      autoactivate = autoactivatedPanelNames.length > 0;
      // remove duplicates in autoactivatedPanelNames/allowedPanel names, but keep order.
      // Make sure autoactivated panel names are in the front of allowedPanelNames.
      // Not sure how to handle different priorities... as things
      // stand, first panel dominates. Maybe interleave? Rarely an issue.
    }
    if (change) {
      this.panelManager.resetPercent();
    }
  }

  nextPanelToMinimize() {
    const panels = [];
    this.collection.each((model) => {
      const column = this.children.findByModel(model);
      column.collection.each((levelModel) => {
        const level = column.children.findByModel(levelModel),
              panel = level.nextPanelToMinimize();
        if (panel) {
          panels.push(panel);
        }
      });
    });
    if (panels.length) {
      return panels[0];
    }
  }
  nextPanelToUnminimize() {
    const panels = [];
    this.collection.each((model) => {
      const column = this.children.findByModel(model);
      column.collection.each((levelModel) => {
        const level = column.children.findByModel(levelModel),
              panel = level.nextPanelToUnminimize();
        if (panel) {
          panels.push(panel);
        }
      });
    });
    if (panels.length) {
      // TODO: Sort by depth
      panels.reverse();
      return panels[0];
    }
  }
  getMinWidth() {
    const columns = this.getColumns();
    let width = 0;
    columns.each((column) => {
      width += column.getMinWidth();
    });
    return width;
  }
  getMaxWidth() {
    const columns = this.getColumns();
    let width = 0;
    columns.each((column) => {
      width += column.getMaxWidth();
    });
    return width;
  }
  updateMinimize(panelLevel) {
    if (panelLevel.minimized) {
      // level was just minimized, recreate that panel and all panels
      // of that column (should all be minimized)
      // in the next column (if any.)
      assert(panelLevel.indexInColumn()
        == panelLevel.panelColumn.collection.length - 1,
        "should be last level");
      var sourceCol = panelLevel.panelColumn,
          targetCol = this.nextColumn(sourceCol);
      if (targetCol) {
        var models = sourceCol.collection.models.slice();
        if (models.length > 1) {
          assert(_.all(models, (model) => !!model.get('minimized')), "previous models should be minimized");
        }
        sourceCol.collection.remove(models);
        targetCol.collection.add(models, {at: 0});
        this.collection.remove(sourceCol.model);
        this.render();
      }
    } else {
      // level was just maximized, shift it (and previous minimized levels)
      // to new previous column. Not needed if last level
      const nextLevel = this.nextLevel(panelLevel);
      if (nextLevel) {
        const colNum = panelLevel.panelColumn.indexInColumns();
        this.collection.add(new PanelColumnModel(), {at: colNum});
        const sourceCol = panelLevel.panelColumn,
              targetCol = this.children.findByModel(this.collection.at(colNum)),
              levelIndex = panelLevel.indexInColumn(),
              models = sourceCol.collection.models.slice(0, levelIndex + 1);
        sourceCol.collection.remove(models);
        targetCol.collection.add(models);
      }
    }
  }
  resetPercent(minWidth) {
    this.children.each((column) => {
      column.resetPercent(minWidth);
    });
  }
}


/**
 * @class app.views.views.PanelGroup
 */
export class PanelGroup extends Marionette.View.extend({
  template: _.template("<div class='group-header'>G<%= groupN %><button class='closeButton'>x</button></div><div class='columns'></div>"),
  ui: {
    closeButton: ".closeButton",
    columns: ".columns",
  },
  regions: {
    columns: "@ui.columns",
  },
  className: 'panel-group',
  rootName: '',
}) {
  initialize(options) {
    this.minimized = !!this.model.get('minimized');
    this.rootName = options.rootName;
    this.collection = this.model.get('collection');
    this.panelManager = options.panelManager;
    options.panelGroup = this;
    this.columnsC = new PanelColumnCollection(options);
    this.selection = {};
  }

  indexInManager() {
    return this.panelManager.collection.indexOf(this.model);
  }

  updateMinimize(panel) {
    // TODO: Rewrite as columns
    const minimized = _.all(this.getLevels(), (p) => p.minimized);
    if (minimized !== this.minimized) {
      // console.log("setting min of group G"+this.indexInManager()+" to "+minimized);
      if (minimized) {
        this.$el.addClass('minimized');
      } else {
        this.$el.removeClass('minimized');
      }
      this.minimized = minimized;
    }
  }

  serializeData() {
    return {
      groupN: this.indexInManager(),
    };
  }

  getLevels() {
    return this.columnsC.getLevels();
  }
  getSelection() {
    return this.selection;
  }
  onRender() {
    this.showChildView('columns', this.columnsC);
  }
  removeLastLevel() {
    this.columnsC.removeLastLevel();
  }
  nextPanelToMinimize() {
    return this.columnsC.nextPanelToMinimize();
  }
  nextPanelToUnminimize() {
    return this.columnsC.nextPanelToUnminimize();
  }
  getMinWidth() {
    return this.columnsC.getMinWidth();
  }
  getMaxWidth(panel) {
    return this.columnsC.getMaxWidth();
  }
  changeSelection(selectionChanges) {
    _.extend(this.selection, selectionChanges);
    return this.columnsC.changeSelection(selectionChanges);
  }
  resetPercent(minWidth) {
    const myMinWidth = this.getMinWidth();
    this.$el.css("width", (100.0*myMinWidth/minWidth)+"%");
    this.columnsC.resetPercent(myMinWidth);
  }
}


/**
 * @class app.views.views.PanelManager
 */
export class PanelManager extends Marionette.CollectionView.extend({
  className: 'panel-manager fitting',
  leftMargin: 5,
  rightMargin: 5,
  groupMargin: 5,
  fitToWindow: true,
  childView: PanelGroup,
  panelClassesByName: {},
}) {
  initialize(options) {
    this.rootName = options.rootName;
    this.model = new PanelManagerModel();
    this.collection = this.model.get('collection');
    this.collection.add(new PanelGroupModel());
    this.resize = _.throttle((newWidth) => this.resizeBase(newWidth), 100, { leading: false });
    this.resetPercent = _.throttle(() => this.resetPercentBase(), 100, { leading: false });
    this.resetPercent();
  }
  childViewOptions(view, index) {
    return {
      rootName: this.rootName,
      panelManager: this,
    };
  }
  getGroups() {
    return this.children;
  }
  registerPanelClass(cls) {
    // called on the prototype
    this.panelClassesByName[cls.prototype.name] = cls;
  }
  createPanelByName(name) {
    // called on the prototype
    const cls = this.panelClassesByName[name];
    if (cls != null) {
      return new cls(arguments);
    }
  }

  canFit(width) {
    const minWidth = this.getMinWidth(); // ordered somehow
    return minWidth <= width;
  }
  setFitToWindow(fitToWindow) {
    if (this.fitToWindow !== fitToWindow) {
      if (fitToWindow) {
        this.$el.addClass('fitting');
      } else {
        this.$el.removeClass('fitting');
      }
      this.fitToWindow = fitToWindow;
    }
    // and recalc css if actually changed.
  }
  updateMinimize(panel) {
    const canFit = this.canFit(window.innerWidth);
    if (this.fitToWindow !== canFit) {
      this.setFitToWindow(canFit);
    }
  }
  getMinWidth(panel) {
    const groups = this.getGroups();
    let previousIsMinimized = false;
    const margin = this.groupMargin;
    let width = -margin;
    groups.each((group) => {
      const groupWidth = group.getMinWidth();
      if (previousIsMinimized) {
        width = Math.min(width, groupWidth);
      } else {
        width += groupWidth + margin;
      }
      previousIsMinimized = group.minimized;
    });
    return width + this.leftMargin + this.rightMargin;
  }

  getMaxWidth(panel) {
    const groups = this.getGroups();
    let previousIsMinimized = false;
    const margin = this.groupMargin;
    let width = -margin;
    groups.each((group) => {
      const groupWidth = group.getMaxWidth();
      if (previousIsMinimized) {
        width = Math.min(width, groupWidth);
      } else {
        width += groupWidth + margin;
      }
      previousIsMinimized = group.minimized;
    });
    return width + this.leftMargin + this.rightMargin;
  }

  getMaxWidth(panel) {
    const groups = this.getGroups();
    let width = this.groupMargin * (groups.length - 1) + this.leftMargin + this.rightMargin;
    groups.each((group) => {
      width += group.getMaxWidth();
    });
    return width;
  }
  nextPanelToMinimize() {
    const groups = this.getGroups(),
          panels = [];
    groups.each((group) => {
      const panel = group.nextPanelToMinimize();
      if (panel != null) {
        panels.push(panel);
      }
    });
    // TODO: Choose the one with the lowest depth... ideally not the latest active group?
    if (panels.length) {
      return panels[0];
    }
  }
  nextPanelToUnminimize() {
    const groups = this.getGroups(),
          panels = [];
    groups.each((group) => {
      const panel = group.nextPanelToUnminimize();
      if (panel != null) {
        panels.push(panel);
      }
    });
    // TODO: Choose the one with the lowest depth... ideally not the latest active group?
    if (panels.length) {
      return panels[0];
    }
  }

  resetPercentBase() {
    const minWidth = this.getMinWidth();
    this.children.each((group) => {
      group.resetPercent(minWidth);
    });
  }


  resizeBase(newWidth) {
    // cases:
    // not fitting, growing: see if fits. if so, fall to next step.
    // fit, growing: unminimize while fits.
    // fit, growing smaller: if stops fitting, minimize until fits? not sure.
    // not fitting, growing smaller: do nothing.
    // TODO: Add a delay function to this, and make sure it does not happen too often
    let nextPanelWidth,
        change = false,
        minWidth = this.getMinWidth(),
        canFit = minWidth <= newWidth;
    while (canFit) {
      const panel = this.nextPanelToUnminimize();
      if (panel == undefined) {
        // TODO Can we minimize a group, in that case?
        break;
      }
      nextPanelWidth = panel.getMinWidth();
      if (minWidth + nextPanelWidth > newWidth) {
        break;
      }
      panel.setMinimize(false);
      change = true;
      minWidth = this.getMinWidth();
      canFit = this.canFit(newWidth);
    }
    if (this.fitToWindow && ! canFit) {
      while (!canFit) {
        const panel = this.nextPanelToMinimize();
        if (panel == undefined) {
          break;
        }
        panel.setMinimize(true);
        change = true;
        minWidth = this.getMinWidth();
        canFit = this.canFit(newWidth);
      }
    }
    if (canFit && !this.fitToWindow) {
      this.setFitToWindow(canFit);
    }
    if (change) {
      this.resetPercent();
    }
  }
}
