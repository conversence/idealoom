/**
 * Represents an announcement, a mutable message-like object, with an author and a date
 * @module app.models.announcement
 */
import $ from "jquery";
import Promise from "bluebird";
import Base from "./base.js";
import i18n from "../utils/i18n.js";
import Ctx from "../common/context.js";
import LangString from "./langstring.js";
import Types from "../utils/types.js";

/**
 * Annoucement model
 * Frontend model for :py:class:`assembl.models.announcement.Announcement`
 * @class app.models.announcement.AnnouncementModel
 * @extends app.models.base.BaseModel
 */
class AnnouncementModel extends Base.Model.extend({
    /**
     * Defaults
     * @type {Object}
     */
    defaults: {
        creator: undefined,
        last_updated_by: undefined,
        title: null,
        body: null,
        idObjectAttachedTo: undefined,
        //Only for idea announcements
        should_propagate_down: undefined,
    },
}) {
    /**
     * Returns an error message if the model format is invalid with th associated id
     * @returns {String}
     * @function app.models.announcement.AnnouncementModel.initialize
     */
    initialize(options) {
        this.on("invalid", function (model, error) {
            console.log(model.id + " " + error);
        });
    }

    /**
     * Returns the attributes hash to be set on the model
     * @function app.models.announcement.AnnouncementModel.parse
     */
    parse(resp, options) {
        var that = this;
        if (resp.title !== undefined) {
            resp.title = new LangString.Model(resp.title, { parse: true });
        }
        if (resp.body !== undefined) {
            resp.body = new LangString.Model(resp.body, { parse: true });
        }
        return super.parse(...arguments);
    }

    /**
     * Returns an error message if one of those attributes (idObjectAttachedTo, last_updated_by, creator) is missing
     * @returns {String}
     * @function app.models.announcement.AnnouncementModel.validate
     */
    validate(attrs, options) {
        if (!this.get("idObjectAttachedTo")) {
            return "Object attached to is missing";
        }
        if (!this.get("last_updated_by")) {
            return "Attached document is missing";
        }
        if (!this.get("creator")) {
            return "Creator is missing";
        }
    }

    /**
     * Returns a promise for the post's creator
     * @returns {Promise}
     * @function app.models.announcement.AnnouncementModel.getCreatorPromise
     */
    getCreatorPromise() {
        var that = this;
        return this.collection.collectionManager
            .getAllUsersCollectionPromise()
            .then(function (allUsersCollection) {
                var creatorModel = allUsersCollection.get(that.get("creator"));
                if (creatorModel) {
                    return Promise.resolve(creatorModel);
                } else {
                    return Promise.reject(
                        "Creator " +
                            that.get("creator") +
                            " not found in allUsersCollection"
                    );
                }
            });
    }
}

/**
 * Annoucements collection
 * @class app.models.announcement.AnnouncementCollection
 * @extends app.models.base.BaseCollection
 */
class AnnouncementCollection extends Base.Collection.extend({
    /**
     * @type {string}
     */
    url: Ctx.getApiV2DiscussionUrl("announcements"),

    /**
     * The model
     * @type {AnnouncementModel}
     */
    model: AnnouncementModel,
}) {}

export default {
    Model: AnnouncementModel,
    Collection: AnnouncementCollection,
};
