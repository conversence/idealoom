/**
 * Represents a discussion
 * @module app.models.publicationFlow
 */
import Base from './base.js';

import Jed from 'jed';
import Ctx from '../common/context.js';
import Permissions from '../utils/permissions.js';
import i18n from '../utils/i18n.js';
import Types from '../utils/types.js';

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
    states: [],
    transitions: [],
  },
  /**
   * @function app.models.publicationFlow.publicationFlowModel.constructor
   */
  constructor: function publicationFlowModel() {
    Base.Model.apply(this, arguments);
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
  }
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
  url: Ctx.getApiV2DiscussionUrl(),
  /**
   * Defaults
   * @type {Object}
   */
  defaults: {
    label: '',
    states: [],
    transitions: [],
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
  validate: function(attrs, options) {
    /**
     * check typeof variable
     * */
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
  constructor: function publicationStateCollection(publicationFlowModel) {
    Base.Collection.apply(this, arguments);
    this.url = publicationFlowModel.url+"/states"
  }
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
  url: Ctx.getApiV2DiscussionUrl(),
  /**
   * Defaults
   * @type {Object}
   */
  defaults: {
    label: '',
    states: [],
    transitions: [],
  },
  /**
   * @function app.models.publicationFlow.publicationTransitionModel.constructor
   */
  constructor: function publicationTransitionModel() {
    Base.Model.apply(this, arguments);
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
  constructor: function publicationTransitionCollection(publicationFlowModel) {
    Base.Collection.apply(this, arguments);
    url = publicationTransitionModel.url + "/transitions"
  }
});

export default {
  publicationFlowModel: publicationFlowModel,
  publicationFlowCollection: publicationFlowCollection,
  publicationStateModel: publicationStateModel,
  publicationStateCollection: publicationStateCollection,
  publicationTransitionModel: publicationTransitionModel,
  publicationTransitionCollection: publicationTransitionCollection,
};
