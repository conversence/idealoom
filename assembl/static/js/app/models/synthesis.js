/**
 * The collection of idea snapshots in a synthesis
 * @module app.models.synthesis
 */

import Base from './base.js';

import Ctx from '../common/context.js';
import Idea from './idea.js';
import i18n from '../utils/i18n.js';


/**
 * Synthesis ideas collection
 * @class app.models.synthesis.SynthesisIdeaCollection
 * @extends app.models.idea.IdeaCollection
 */

class SynthesisIdeaCollection extends Idea.Collection.extend({
  // Here I actually need double inheritance; cheating with function references.
  add: Base.RelationsCollection.prototype.add,

  remove: Base.RelationsCollection.prototype.remove
}) {
  initialize(models, options) {
    var synthesis = options.synthesis;
    var id = synthesis.getNumericId();
    this.url = Ctx.getApiV2DiscussionUrl("/syntheses/" + id + "/ideas");
  }
}

/**
 * Synthesis model
 * Frontend model for :py:class:`assembl.models.idea_graph_view.Synthesis`
 * @class app.models.synthesis.SynthesisModel
 * @extends app.models.base.BaseModel
 */

class SynthesisModel extends Base.Model.extend({
  /**
   * The urlRoot endpoint
   * @type {string}
   */
  urlRoot: Ctx.getApiUrl('explicit_subgraphs/synthesis'),

  /**
   * Default values
   * @type {Object}
   */
  defaults: {
    subject: i18n.gettext('Add a title'),
    introduction: i18n.gettext('Add an introduction'),
    conclusion: i18n.gettext('Add a conclusion'),
    ideas: [],
    published_in_post: null
  }
}) {
  /**
   * @init
   */
  initialize() {
    //What was this?  Benoitg - 2014-05-13
    //this.on('change', this.onAttrChange, this);
  }

  validate(attrs, options) {
    /**
     * check typeof variable
     * */
  }

  set(key, val, options) {
    var ob = super.set(...arguments);
    if ((key == "ideas" || key.ideas !== undefined) && this.ideasCollection !== undefined) {
        this.ideasCollection.reset(this.get("ideas"), {parse: true});
    }
    return ob;
  }

  getIdeasCollection() {
    if (this.ideasCollection === undefined) {
        // cache since it is the result of parsing.
        this.ideasCollection = new SynthesisIdeaCollection(
            this.get("ideas"), {parse: true, synthesis: this});
        //this.ideasCollection.collectionManage = collectionManager;
    }
    return this.ideasCollection;
  }
}

/**
 * Synthesis collection
 * @class app.models.synthesis.SynthesisCollection
 * @extends app.models.base.BaseCollection
 */

class SynthesisCollection extends Base.Collection.extend({
  /**
   * Url
   * @type {string}
   */
  url: Ctx.getApiUrl("explicit_subgraphs/synthesis"),

  /**
   * The model
   * @type {SynthesisModel}
   */
  model: SynthesisModel
}) {
  getPublishedSyntheses() {
      return this.filter(function(model) { return model.get('published_in_post') != null; });
    }

  /** Get the last published synthesis
   * @returns Message.Model or null
   */
  getLastPublisedSynthesis() {
    var publishedSyntheses = this.getPublishedSyntheses();
    var lastSynthesis = null;
    if (publishedSyntheses.length > 0) {
      _.sortBy(publishedSyntheses, function(model) {
        return model.get('created');
      });
      lastSynthesis = _.last(publishedSyntheses);
    }

    return lastSynthesis;
  }
}

export default {
  Model: SynthesisModel,
  Collection: SynthesisCollection
};

