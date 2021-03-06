/**
 *
 * @module app.views.user.userNavigationMenu
 */

import $ from "jquery";
import i18n from "../../utils/i18n.js";
import Ctx from "../../common/context.js";
import CollectionManager from "../../common/collectionManager.js";
import Roles from "../../utils/roles.js";
import RoleModels from "../../models/roles.js";
import LoaderView from "../loaderView.js";
import Permissions from "../../utils/permissions.js";

class userNavigationMenu extends LoaderView.extend({
    template: "#tmpl-userNavigationMenu",
    tagName: "nav",
    className: "sidebar-nav",
    selectedSection: undefined,
}) {
    initialize(options) {
        var that = this;
        var collectionManager = new CollectionManager();

        if ("selectedSection" in options) {
            this.selectedSection = options.selectedSection;
        }
        var user = Ctx.getCurrentUser();
        if (user.isUnknownUser()) {
            this.localRoles = new RoleModels.myLocalRoleCollection();
        } else {
            this.setLoading(true);
            collectionManager
                .getMyLocalRoleCollectionPromise()
                .then(function (localRoles) {
                    if (!that.isDestroyed()) {
                        that.localRoles = localRoles;
                        that.setLoading(false);
                        that.render();
                    }
                });
        }
    }

    serializeData() {
        if (this.isLoading()) {
            return {};
        }
        return {
            selectedSection: this.selectedSection,
            currentUser: Ctx.getCurrentUser(),
            Permissions: Permissions,
            Roles: Roles,
            localRoles: this.localRoles,
        };
    }
}

export default userNavigationMenu;
