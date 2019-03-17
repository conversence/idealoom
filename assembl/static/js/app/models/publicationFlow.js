/**
 * Represents a discussion
 * @module app.models.publicationFlow
 */
import Base from './base.js';

import Ctx from '../common/context.js';
import Types from '../utils/types.js';
import LangString from './langstring.js';

/**
 * PublicationFlow model
 * Frontend model for :py:class:`assembl.models.publication_states.PublicationFlow`
 * @class app.models.publicationFlow.publicationFlowModel
 * @extends app.models.base.BaseModel
 */
var publicationFlowModel = Base.Model.extend({
  /**
   * @member {string} app.models.publicationFlow.publicationFlowModel.url
   */
  urlRoot: Ctx.getApiV2Url(Types.PUBLICATION_FLOW),
  /**
   * Defaults
   * @type {Object}
   */
  defaults: {
    label: '',
    states: null,
    transitions: null,
  },
  /**
   * @function app.models.publicationFlow.publicationFlowModel.constructor
   */
  constructor: function publicationFlowModel() {
    Base.Model.apply(this, arguments);
  },
  parse: function(rawModel, options) {
    if (rawModel) {
      rawModel.states = new publicationStateCollection(rawModel.states, {parse: true, flow: this});
      rawModel.transitions = new publicationTransitionCollection(rawModel.transitions, {parse: true, flow: this});
      if (rawModel.name) {
        rawModel.name = new LangString.Model(rawModel.name, {parse: true});
      }
    }
    return rawModel;
  },
  /**
   * Validate the model attributes
   * @function app.models.publicationFlow.publicationFlowModel.validate
   */
  validate: function(attrs, options) {
    /**
     * check typeof variable
     * */
  },
});

/**
 * Discussions collection
 * @class app.models.publicationFlow.publicationFlowCollection
 * @extends app.models.base.BaseCollection
 */
var publicationFlowCollection = Base.Collection.extend({
  /**
   * @member {string} app.models.publicationFlow.publicationFlowCollection.url
   */
  url: Ctx.getApiV2Url(Types.PUBLICATION_FLOW)+"?view=changes",
  /**
   * The model
   * @type {publicationFlowModel}
   */
  model: publicationFlowModel,
  /**
   * @function app.models.publicationFlow.publicationFlowCollection.constructor
   */
  constructor: function publicationFlowCollection() {
    Base.Collection.apply(this, arguments);
  },
});


/**
 * PublicationState model
 * Frontend model for :py:class:`assembl.models.publication_states.PublicationState`
 * @class app.models.publicationFlow.publicationStateModel
 * @extends app.models.base.BaseModel
 */
var publicationStateModel = Base.Model.extend({
  /**
   * @member {string} app.models.publicationStateModel.publicationStateModel.url
   */
  urlRoot: Ctx.getApiV2Url(Types.PUBLICATION_STATE),
  /**
   * Defaults
   * @type {Object}
   */
  defaults: {
    label: '',
    name: null,
    flow: null,
  },
  /**
   * @function app.models.publicationFlow.publicationStateModel.constructor
   */
  constructor: function publicationStateModel() {
    Base.Model.apply(this, arguments);
  },
  /**
   * Validate the model attributes
   * @function app.models.publicationFlow.publicationStateModel.validate
   */
  parse: function(rawModel, options) {
    if (rawModel.name) {
      rawModel.name = new LangString.Model(rawModel.name, {parse: true});
    }
    rawModel.flow = options.flow || rawModel.flow;

    return rawModel;
  },
  validate: function(attrs, options) {
    /**
     * check typeof variable
     * */
  },
  nameOrLabel(langPrefs) {
    const name = this.get('name');
    if (name) {
      return name.bestValue(langPrefs);
    } else {
      return this.get('label');
    }
  },
});
/**
 * Discussions collection
 * @class app.models.publicationFlow.publicationStateCollection
 * @extends app.models.base.BaseCollection
 */
var publicationStateCollection = Base.Collection.extend({
  /**
   * The model
   * @type {publicationStateModel}
   */
  model: publicationStateModel,
  /**
   * @function app.models.publicationFlow.publicationStateCollection.constructor
   */
  constructor: function publicationStateCollection(data, options) {
    Base.Collection.apply(this, arguments);
    this.flow = options.flow;
    if (this.flow) {
      this.url = this.flow.url()+"/states";
    }
  },
  findByLabel: function(label) {
    const stateA = this.filter((state) => {return state.get('label') == label});
    if (stateA && stateA.length)
      return stateA[0];
  },
});

/**
 * PublicationTransition model
 * Frontend model for :py:class:`assembl.models.publication_states.PublicationTransition`
 * @class app.models.publicationFlow.publicationTransitionModel
 * @extends app.models.base.BaseModel
 */
var publicationTransitionModel = Base.Model.extend({
  /**
   * @member {string} app.models.publicationTransitionModel.publicationTransitionModel.url
   */
  urlRoot: Ctx.getApiV2Url(Types.PUBLICATION_TRANSITION),
  /**
   * Defaults
   * @type {Object}
   */
  defaults: {
    label: '',
    name: null,
    source: null,
    source_label: '',
    target: null,
    target_label: '',
    flow: null,
    req_permission_name: '',
  },
  /**
   * @function app.models.publicationFlow.publicationTransitionModel.constructor
   */
  constructor: function publicationTransitionModel() {
    Base.Model.apply(this, arguments);
  },
  parse: function(rawModel, options) {
    if (rawModel.name) {
      rawModel.name = new LangString.Model(rawModel.name, {parse: true});
    }
    rawModel.flow = options.flow || rawModel.flow;
    
    return rawModel;
  },
  /**
   * Validate the model attributes
   * @function app.models.publicationFlow.publicationTransitionModel.validate
   */
  validate: function(attrs, options) {
    /**
     * check typeof variable
     * */
  },
  nameOrLabel(langPrefs) {
    const name = this.get('name');
    if (name) {
      return name.bestValue(langPrefs);
    } else {
      return this.get('label');
    }
  },
});
/**
 * Discussions collection
 * @class app.models.publicationFlow.publicationTransitionCollection
 * @extends app.models.base.BaseCollection
 */
var publicationTransitionCollection = Base.Collection.extend({
  /**
   * The model
   * @type {publicationTransitionModel}
   */
  model: publicationTransitionModel,
  /**
   * @function app.models.publicationFlow.publicationTransitionCollection.constructor
   */
  constructor: function publicationTransitionCollection(data, options) {
    Base.Collection.apply(this, arguments);
    this.flow = options.flow;
    if (this.flow) {
      this.url = this.flow.url()+"/transitions";
    }
  },
});

export default {
  publicationFlowModel: publicationFlowModel,
  publicationFlowCollection: publicationFlowCollection,
  publicationStateModel: publicationStateModel,
  publicationStateCollection: publicationStateCollection,
  publicationTransitionModel: publicationTransitionModel,
  publicationTransitionCollection: publicationTransitionCollection,
};
