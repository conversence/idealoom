/**
 * An action done by a user.
 * @module app.models.actions
 */
import Base from './base.js';

import Ctx from '../common/context.js';

/**
 * Action model
 * Frontend model for :py:class:`assembl.models.action.Action`
 * @class app.models.actions.actionModel
 * @extends app.models.base.BaseModel
 */
class actionModel extends Base.Model.extend({
 /**
  * @member {string} app.models.actions.actionModel.urlRoot
  */
 urlRoot: Ctx.getApiV2DiscussionUrl("/all_users/current/actions"),

 /**
  * Defaults
  * @type {Object}
  */
 defaults: {
   what: null,
   user: null,
   target_type: "Content",
   '@id': null,
   '@type': null,
   '@view': null
 }
}) {
 /**
  * Validate the model attributes
  * @function app.models.actions.actionModel.validate
  */
 validate(attrs, options) {
   /**
    * check typeof variable
    * */
 }
}

/**
 * Actions collection
 * @class app.models.actions.actionCollection
 * @extends app.models.base.BaseCollection
 */
class actionCollection extends Base.Collection.extend({
 /**
  * @member {string} app.models.actions.actionCollection.url
  */
 url: Ctx.getApiV2DiscussionUrl("/all_users/current/actions"),

 /**
  * The model
  * @type {actionModel}
  */
 model: actionModel
}) {}

export default {
  Model: actionModel,
  Collection: actionCollection
};
