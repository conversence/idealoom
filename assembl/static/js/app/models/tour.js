/**
 * A tour manager to help user
 * @module app.models.tour
 */

import Base from "./base.js";

import $ from "jquery";
import Ctx from "../common/context.js";

/**
 * Tour model
 * @class app.models.tour.tourModel
 * @extends app.models.base.BaseModel
 */

class tourModel extends Base.Model.extend({
    urlRoot: Ctx.getApiV2DiscussionUrl("user_ns_kv/tour_seen"),

    defaults: {
        on_start: false,
        on_show_synthesis: false,
    },
}) {
    clear() {
        this.delete();
    }

    isSeen(name) {
        var that = this;
        if (!this.get(name)) {
            $.ajax(this.urlRoot + "/" + name, {
                data: "true",
                contentType: "application/json",
                method: "PUT",
                complete: function () {
                    that.set(name, true);
                },
            });
        }
    }

    fetch(options) {
        options = options || {};
        options.cache = false; // for IE cache (GET -> PUT -> GET) http://stackoverflow.com/questions/6178366/backbone-js-fetch-results-cached/8966486#8966486
        return Backbone.Collection.prototype.fetch.call(this, options);
    }
}

export default {
    Model: tourModel,
};
