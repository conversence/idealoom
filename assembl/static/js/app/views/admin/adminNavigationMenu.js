/**
 *
 * @module app.views.admin.adminNavigationMenu
 */

import Marionette from "backbone.marionette";

import $ from "jquery";
import i18n from "../../utils/i18n.js";
import Permissions from "../../utils/permissions.js";
import Ctx from "../../common/context.js";

class adminNavigationMenu extends Marionette.View.extend({
    tagName: "nav",
    className: "sidebar-nav",
    selectedSection: undefined,
}) {
    initialize(options) {
        if ("selectedSection" in options) {
            this.selectedSection = options.selectedSection;
        }
    }

    serializeData() {
        return {
            selectedSection: this.selectedSection,
            is_sysadmin: Ctx.getCurrentUser().can(Permissions.SYSADMIN),
        };
    }
}

class discussionAdminNavigationMenu extends adminNavigationMenu.extend({
    template: "#tmpl-discussionAdminNavigationMenu",
}) {}

class globalAdminNavigationMenu extends adminNavigationMenu.extend({
    template: "#tmpl-globalAdminNavigationMenu",
}) {}

export default {
    discussionAdminNavigationMenu: discussionAdminNavigationMenu,
    globalAdminNavigationMenu: globalAdminNavigationMenu,
};
