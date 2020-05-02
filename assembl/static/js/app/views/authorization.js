/**
 *
 * @module app.views.authorization
 */

import Ctx from "../common/context.js";
import { View } from "backbone.marionette";

class authorization extends View.extend({
    template: "#tmpl-authorization",
    className: "authorization",
}) {
    initialize(options) {
        this.error = options.error;
        this.message = options.message;
    }

    serializeData() {
        return {
            error: this.error,
            message: this.message,
        };
    }

    templateContext() {
        return {
            urlLogIn: function () {
                return "/login?next=/" + Ctx.getDiscussionSlug() + "/";
            },
        };
    }
}

export default authorization;
