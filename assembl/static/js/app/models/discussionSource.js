/**
 * Represents a discussion's messages from an external source.
 * @module app.models.discussionSource
 */
import Base from "./base.js";

import Ctx from "../common/context.js";
import $ from "jquery";

/**
 * Source model
 * Frontend model for :py:class:`assembl.models.generic.ContentSource`
 * @class app.models.discussionSource.sourceModel
 * @extends app.models.base.BaseModel
 */
class sourceModel extends Base.Model.extend({
    /**
     * @member {string} app.models.discussionSource.sourceModel.urlRoot
     */
    urlRoot: Ctx.getApiV2DiscussionUrl() + "sources",

    /**
     * Defaults
     * @type {Object}
     */
    defaults: {
        name: "",
        admin_sender: "",
        post_email_address: "",
        created: "",
        host: "",
        discussion_id: "",
        "@type": "",
        folder: "",
        use_ssl: false,
        port: 0,
    },
}) {
    /**
     * Validate the model attributes
     * @function app.models.discussionSource.sourceModel.validate
     */
    validate(attrs, options) {
        /**
         * check typeof variable
         * */
    }

    /**
     * Run import to backend server
     * @function app.models.discussionSource.sourceModel.doReimport
     */
    doReimport() {
        var url = this.url() + "/fetch_posts";
        return $.post(url, { reimport: true });
    }

    /**
     * Run process to backend server
     * @function app.models.discussionSource.sourceModel.doReprocess
     */
    doReprocess() {
        var url = this.url() + "/fetch_posts";
        return $.post(url, { reprocess: true });
    }
}

/**
 * Sources collection
 * @class app.models.discussionSource.sourceCollection
 * @extends app.models.base.BaseCollection
 */
class sourceCollection extends Base.Collection.extend({
    /**
     * @member {string} app.models.discussionSource.sourceCollection.urlRoot
     */
    url: Ctx.getApiV2DiscussionUrl() + "sources",

    /**
     * The model
     * @type {sourceModel}
     */
    model: sourceModel,
}) {}

export default {
    Model: sourceModel,
    Collection: sourceCollection,
};
