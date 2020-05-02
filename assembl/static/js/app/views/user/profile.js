/**
 *
 * @module app.views.user.profile
 */

import $ from "jquery";
import Agents from "../../models/agents.js";
import i18n from "../../utils/i18n.js";
import UserNavigationMenu from "./userNavigationMenu.js";
import Ctx from "../../common/context.js";
import Growl from "../../utils/growl.js";
import { View } from "backbone.marionette";

class profile extends View.extend({
    template: "#tmpl-userProfile",
    className: "admin-profile",

    ui: {
        close: ".bx-alert-success .bx-close",
        profile: ".js_saveProfile",
        form: ".core-form .form-horizontal",
    },

    regions: {
        navigationMenuHolder: ".navigation-menu-holder",
    },

    modelEvents: {
        "change sync": "render",
    },

    events: {
        "click @ui.profile": "saveProfile",
        "click @ui.close": "close",
    },
}) {
    initialize() {
        this.model = new Agents.Model({ "@id": Ctx.getCurrentUserId() });
        this.model.fetch();
    }

    serializeData() {
        return {
            profile: this.model,
        };
    }

    onRender() {
        // this is in onRender instead of onBeforeRender because of the modelEvents
        var menu = new UserNavigationMenu({ selectedSection: "profile" });
        this.showChildView("navigationMenuHolder", menu);
    }

    saveProfile(e) {
        e.preventDefault();

        var real_name = this.$('input[name="real_name"]').val();

        this.model.set({ real_name: real_name });

        this.model.save(null, {
            success: function (model, resp) {
                Growl.showBottomGrowl(
                    Growl.GrowlReason.SUCCESS,
                    i18n.gettext("Your settings were saved!")
                );
            },
            error: function (model, resp) {
                Growl.showBottomGrowl(
                    Growl.GrowlReason.ERROR,
                    i18n.gettext("Your settings failed to update.")
                );
            },
        });
    }
}

export default profile;
