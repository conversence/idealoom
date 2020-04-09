/**
 * Custom key-value storage bound to a user and a namespace
 * @module app.models.userCustomData
 */

import Backbone from "backbone";

import Ctx from "../common/context.js";

// We do not use Base.Model.extend(), because we want to keep Backbone's default behaviour with model urls
/**
 * User custom data model
 * Frontend model for :py:class:`assembl.models.user_key_values.DiscussionPerUserNamespacedKeyValue`
 * @class app.models.userCustomData.UserCustomDataModel
 * @extends Backbone.Model
 */
class UserCustomDataModel extends Backbone.Model.extend({
    urlRoot: Ctx.getApiV2DiscussionUrl("user_ns_kv"),
}) {}

export default {
    Model: UserCustomDataModel,
};
