/**
 * Discussion preferences
 * @module app.models.discussionPreference
 */
import Backbone from "backbone";

import Types from "../utils/types.js";
import Ctx from "../common/context.js";

/**
 * An individual preference value.
 * We do not use Base.Model.extend(), because we want to keep Backbone's default behaviour with model urls.
 * Generic case: preference value can be any json, not necessarily a dict.
 * So put it in "value" attribute of this model.
 * @class app.models.discussionPreference.DiscussionIndividualPreferenceModel
 */
class DiscussionIndividualPreferenceModel extends Backbone.Model {
    /**
     * @function app.models.discussionPreference.DiscussionIndividualPreferenceModel.parse
     */
    parse(resp, options) {
        this._subcollectionCache = undefined;
        if (resp.value !== undefined && resp.id !== undefined) return resp;
        return { value: resp };
    }

    /**
     * @function app.models.discussionPreference.DiscussionIndividualPreferenceModel.toJSON
     */
    toJSON(options) {
        return _.clone(this.get("value"));
    }

    /**
     * @function app.models.discussionPreference.DiscussionIndividualPreferenceModel.valueAsCollection
     * The preference is a list or dict of something. Return a collection of that something, or dict items.
     */
    valueAsCollection(preferenceData, as_list) {
        // MISSING: Better handling of default_item_X and default_Key...
        if (this._subcollectionCache === undefined) {
            var collection;
            var that = this;
            var value = this.get("value");
            if (as_list) {
                if (!Array.isArray(value)) {
                    // Error in value type
                    // shallow clone, hopefully good enough
                    value = _.clone(preferenceData.default);
                    this.set("value", value);
                }
                collection = new DiscussionPreferenceSubCollection(value, {
                    parse: true,
                });
                this.listenTo(collection, "reset change add remove", function (
                    model
                ) {
                    var val = model.collection.map(function (aModel) {
                        return aModel.get("value");
                    });
                    that.set("value", val);
                });
            } else {
                if (!_.isObject(value)) {
                    // Error in value type
                    // shallow clone, hopefully good enough
                    value = _.clone(preferenceData.default);
                    this.set("value", value);
                }
                // In that case, transform {"value": {k,v}} into [{"key":k, "value": v}]
                var items = [];
                _.mapObject(value, function (v, k) {
                    items.push({ key: k, value: v });
                });
                collection = new DiscussionPreferenceSubCollection(items);
                this.listenTo(collection, "reset change add remove", function (
                    model
                ) {
                    var val = {};
                    model.collection.map(function (aModel) {
                        val[aModel.get("key")] = aModel.get("value");
                    });
                    that.set("value", val);
                });
            }
            this._subcollectionCache = collection;
        }
        return this._subcollectionCache;
    }
}

/**
 * Subcase: pref is a dictionary, so we can use normal backbone
 * @class app.models.discussionPreference.DiscussionPreferenceDictionaryModel
 */
class DiscussionPreferenceDictionaryModel extends Backbone.Model {
    /**
     * @function app.models.discussionPreference.DiscussionPreferenceDictionaryModel.url
     */
    url() {
        return Ctx.getApiV2DiscussionUrl("settings/" + this.id);
    }

    /**
     * @function app.models.discussionPreference.DiscussionIndividualPreferenceModel.valueAsCollection
     * The preference is a list of something. Return a collection of that something.
     */
    valueAsCollection() {
        if (this._subcollectionCache !== undefined) {
            return this._subcollectionCache;
        }
        var value = this.get("value");
        var that = this;
        var collection;
        var items = [];
        _.mapObject(value, function (v, k) {
            items.push({ key: k, value: v });
        });
        collection = new DiscussionPreferenceSubCollection(items, {
            parse: true,
        });
        this.listenTo(collection, "reset change add remove", function (model) {
            var val = {};
            model.collection.map(function (aModel) {
                val[aModel.get("key")] = aModel.get("value");
            });
            that.set("value", val);
        });
        this._subcollectionCache = collection;
        return collection;
    }
}

/**
 * @class app.models.discussionPreference.DiscussionPreferenceSubCollection
 */
class DiscussionPreferenceSubCollection extends Backbone.Collection.extend({
    model: DiscussionIndividualPreferenceModel,
}) {}

/**
 * @class app.models.discussionPreference.PreferenceCollection
 */
class PreferenceCollection extends Backbone.Collection.extend({
    model: DiscussionIndividualPreferenceModel,
}) {
    /**
     * @function app.models.discussionPreference.DiscussionPreferenceCollection.parse
     */
    parse(resp, options) {
        // does this go through model.parse afterwards? That would be trouble.
        var preference_data = resp.preference_data;
        return _.map(preference_data, function (pref_data) {
            var id = pref_data.id;
            return { id: id, value: resp[id] };
        });
    }

    /**
     * @function app.models.discussionPreference.DiscussionPreferenceCollection.toJSON
     */
    toJSON(options) {
        var prefs = {};
        this.models.map(function (m) {
            prefs[m.id] = m.toJson(options);
        });
        return prefs;
    }
}

/**
 * @class app.models.discussionPreference.DiscussionPreferenceCollection
 * @extends app.models.discussionPreference.PreferenceCollection
 */
class DiscussionPreferenceCollection extends PreferenceCollection.extend({
    url: Ctx.getApiV2DiscussionUrl("settings"),
}) {}

/**
 * @class app.models.discussionPreference.DiscussionPreferenceCollection
 * @extends app.models.discussionPreference.PreferenceCollection
 */
class GlobalPreferenceCollection extends PreferenceCollection.extend({
    url: Ctx.getApiV2Url(Types.PREFERENCES + "/default"),
}) {}

/**
 * @class app.models.discussionPreference.UserPreferenceRawCollection
 * @extends app.models.discussionPreference.PreferenceCollection
 */
class UserPreferenceRawCollection extends PreferenceCollection.extend({
    url: Ctx.getApiV2DiscussionUrl("all_users/current/preferences"),
}) {}

export default {
    DictModel: DiscussionPreferenceDictionaryModel,
    DiscussionPreferenceCollection: DiscussionPreferenceCollection,
    GlobalPreferenceCollection: GlobalPreferenceCollection,
    UserPreferenceCollection: UserPreferenceRawCollection,
    Model: DiscussionIndividualPreferenceModel,
};
