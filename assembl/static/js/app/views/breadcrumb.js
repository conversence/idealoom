/**
 * 
 * @module app.views.breadcrumb
 */

import Marionette from 'backbone.marionette';

import $ from 'jquery';
import _ from 'underscore';
import CollectionManager from '../common/collectionManager.js';

/**
 * Generic Breadcrumb ItemView.
 * Must pass a serializer function in order to correctly show the content
 * If not, the passed model will be displayed
 *
 * @param {function} options.serializerFunc  The serializer function taking the passed model and returning a template string
 */
class BreadcrumbItemView extends Marionette.View.extend({
  template: _.template("<%= entity %>"),
  className: 'breadcrumb'
}) {
  // from http://jsfiddle.net/zaSvT/

  initialize(options) {
    this.serializerFunc = options.serializerFunc;
  }

  renderData(serialzedModel) {
    if (!serialzedModel) { return ""; }

    if (this.serializerFunc) {
      return this.serializerFunc(serialzedModel);
    }

    else {
      return serialzedModel;
    }
  }

  serializeData() {
    return {
      entity: this.renderData(this.model)
    }
  }
}

class BreadcrumbCollectionView extends Marionette.CollectionView.extend({
  childView: BreadcrumbItemView
}) {
  initialize(options) {
    this.serializerFunc = options.serializerFunc || null;
    this.listenTo(this.collection, 'change', this.render );
    // this.render();
  }

  childViewOptions() {
    return {
      serializerFunc: this.serializerFunc
    }
  }
}

export default {
  BreadcrumbItemView: BreadcrumbItemView,
  BreadcrumbCollectionView: BreadcrumbCollectionView
};
