/**
 * Represents the state of a panel group (current idea, selected navigation, minimised states, etc.)
 * @module app.models.groupState
 */
import Base from './base.js';

import Idea from './idea.js';

/**
 * Group state model
 * @class app.models.groupState.GroupStateModel
 * @extends app.models.base.BaseModel
 */
class GroupStateModel extends Base.Model.extend({
  /**
   * Defaults
   * @type {Object}
   */
  defaults: {
    currentIdea: null
  }
}) {
  /**
   * Return a copy of the model's attributes for JSON stringification. 
   * @function app.models.groupState.GroupStateModel.toJSON
   */
  toJSON(options) {
    var json = super.toJSON(...arguments);
    if (json.currentIdea !== null && json.currentIdea instanceof Idea.Model) {
      json.currentIdea = json.currentIdea.get("@id");
    }
    return json;
  }

  /**
   * Validate the model attributes and returns an error message if the model is invalid and undefined if the model is valid
   * @function app.models.groupState.GroupStateModel.validate
   */
  validate(attributes, options) {
    if (attributes['currentIdea'] === null) {
      return;
    }
    else if (attributes['currentIdea'] === undefined) {
      return "currentIdea can be null, but not undefined";
    }
    else if (!(attributes.currentIdea instanceof Idea.Model)) {
      return "currentIdea isn't an instance of Idea";
    }
  }
}

/**
 * Group states collection
 * @class app.models.groupState.GroupStates
 * @extends app.models.base.BaseCollection
 */
class GroupStates extends Base.Collection.extend({
  /**
   * The model
   * @type {GroupStateModel}
   */
  model: GroupStateModel
}) {
  /**
   * Validate the model attributes
   * @function app.models.groupState.GroupStates.validate
   */
  validate() {
    var invalid = [];
    this.each(function(groupState) {
      if (!groupState.validate()) {
        invalid.push(groupState);
      }
    });
    if (invalid.length) {
      console.warn("GroupState.Collection: removing " + invalid.length + " invalid groupStates from " + this.length + " groupStates.");
      this.remove(invalid);
      console.warn("GroupState.Collection: after removal, number of remaining valid groupStates: " + this.length);
    }
    return (this.length > 0);
  }
}

export default {
  Model: GroupStateModel,
  Collection: GroupStates
};
