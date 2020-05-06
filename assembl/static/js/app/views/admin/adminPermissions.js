import { View, CollectionView, common } from "backbone.marionette";
import Promise from "bluebird";
import _ from "underscore";
import Growl from "../../utils/growl.js";

import i18n from "../../utils/i18n.js";
import Types from "../../utils/types.js";
import LoaderView from "../loaderView.js";
import CollectionManager from "../../common/collectionManager.js";
import AdminNavigationMenu from "./adminNavigationMenu.js";
import RoleModels from "../../models/roles.js";

class RoleHeaderCell extends View.extend({
    tagName: "th",
    template: _.template("<%= name %>"),
}) {}

class RoleHeaderRow extends CollectionView.extend({
    childView: RoleHeaderCell,
    tagName: "thead",
}) {
    _getBuffer(views) {
        // copied from Marionette... will be hard to keep up to date.
        // But I need the way to prefix an element in-place.
        const elBuffer = this.Dom.createBuffer();
        this.Dom.appendContents(
            elBuffer,
            "<th>" + this.options.cell0 + "</th>"
        );
        this.Dom.appendContents(elBuffer, super._getBuffer(views));

        return elBuffer;
    }

    childViewOptions(model) {
        return {
            parentView: this,
        };
    }
}

class RolePermissionCell extends LoaderView.extend({
    ui: {
        input: ".in",
    },

    events: {
        "click @ui.input": "onClick",
    },

    tagName: "td",
    template: _.template(
        "<input class='in' type='checkbox' <%= checked %> <%= disabled %>/>"
    ),
}) {
    onClick(ev) {
        this.setLoading(true);
        this.render();
        if (ev.currentTarget.checked) {
            this.addPermission();
        } else {
            this.removePermission();
        }
    }

    addPermission() {
        const permission = new RoleModels.discPermModel({
            permission: this.options.permissionName,
            role: this.options.roleName,
            discussion:
                "local:" + Types.DISCUSSION + "/" + Ctx.getDiscussionId(),
        });
        this.options.localPermissions.add(permission);
        permission.save(
            {},
            {
                success: () => {
                    this.options.localPermission = permission;
                    this.setLoading(false);
                    this.render();
                },
                error: (model, resp) => {
                    Growl.showBottomGrowl(
                        Growl.GrowlReason.ERROR,
                        i18n.gettext("Your settings failed to update.")
                    );
                    this.setLoading(false);
                    this.render();
                },
            }
        );
    }

    removePermission() {
        this.options.localPermission.destroy({
            success: () => {
                this.options.localPermission = null;
                this.setLoading(false);
                this.render();
            },
            error: (model, resp) => {
                Growl.showBottomGrowl(
                    Growl.GrowlReason.ERROR,
                    i18n.gettext("Your settings failed to update.")
                );
                this.setLoading(false);
                this.render();
            },
        });
    }

    serializeData() {
        return {
            checked: this.options.localPermission ? "checked='checked'" : "",
            disabled: "",
        };
    }
}

class StateRolePermissionCell extends RolePermissionCell {
    serializeData() {
        return {
            checked:
                this.options.statePermission || this.options.localPermission
                    ? "checked='checked'"
                    : "",
            disabled: this.options.localPermission ? "disabled='disabled'" : "",
        };
    }

    addPermission() {
        const permission = new RoleModels.pubStatePermModel({
            permission: this.options.permissionName,
            role: this.options.roleName,
            state: this.options.stateLabel,
            discussion:
                "local:" + Types.DISCUSSION + "/" + Ctx.getDiscussionId(),
        });
        this.options.statePermissions.add(permission);
        permission.save(
            {},
            {
                success: () => {
                    this.options.statePermission = permission;
                    this.setLoading(false);
                    this.render();
                },
                error: (model, resp) => {
                    Growl.showBottomGrowl(
                        Growl.GrowlReason.ERROR,
                        i18n.gettext("Your settings failed to update.")
                    );
                    this.setLoading(false);
                    this.render();
                },
            }
        );
    }

    removePermission() {
        this.options.statePermission.destroy({
            success: () => {
                this.options.statePermission = null;
                this.setLoading(false);
                this.render();
            },
            error: (model, resp) => {
                Growl.showBottomGrowl(
                    Growl.GrowlReason.ERROR,
                    i18n.gettext("Your settings failed to update.")
                );
                this.setLoading(false);
                this.render();
            },
        });
    }
}

class RolePermissionRow extends CollectionView.extend({
    childView: RolePermissionCell,
    tagName: "tr",
}) {
    childViewOptions(model) {
        const options = this.options;
        const roleName = model.get("name");
        const permissionName = options.model.get("name");
        const localPermission = options.localPermissions.find((lp) => {
            return (
                lp.get("permission") == permissionName &&
                lp.get("role") == roleName
            );
        });
        return {
            parentView: this,
            roleName: roleName,
            permissionName: permissionName,
            localPermissions: options.localPermissions,
            permissionsView: options.permissionsView,
            localPermission: localPermission,
        };
    }

    _getBuffer(views) {
        // copied from Marionette... will be hard to keep up to date.
        // But I need the way to prefix an element in-place.
        const elBuffer = this.Dom.createBuffer();
        this.Dom.appendContents(
            elBuffer,
            "<th>" + this.model.get("name") + "</th>"
        );
        this.Dom.appendContents(elBuffer, super._getBuffer(views));

        return elBuffer;
    }
}

class StateRolePermissionRow extends RolePermissionRow.extend({
    childView: StateRolePermissionCell,
}) {
    childViewOptions(model) {
        const options = this.options;
        const base = super.childViewOptions(...arguments);
        const roleName = model.get("name");
        const permissionName = options.model.get("name");
        const statePermission = options.statePermissions.find((lp) => {
            return (
                lp.get("permission") == permissionName &&
                lp.get("role") == roleName &&
                lp.get("state") == options.stateLabel
            );
        });
        return _.extend(base, {
            stateLabel: options.stateLabel,
            statePermissions: options.statePermissions,
            statePermission: statePermission,
        });
    }
}

class DeleteRoleRow extends RolePermissionRow {}

class RolePermissionTable extends CollectionView.extend({
    childView: RolePermissionRow,
    tagName: "tbody",
}) {
    childViewOptions(model) {
        const options = this.options;
        return {
            parentView: this,
            collection: options.permissionsView.roleCollection,
            localPermissions: options.localPermissions,
            permissionsView: options.permissionsView,
        };
    }
}

class StateRolePermissionTable extends RolePermissionTable.extend({
    childView: StateRolePermissionRow,
}) {
    childViewOptions(model) {
        const options = this.options;
        const base = super.childViewOptions(...arguments);
        return _.extend(base, {
            statePermissions: options.statePermissions,
            stateLabel: options.stateLabel,
        });
    }

    viewFilter(view, index, children) {
        return view.model.get("name").indexOf("Idea") >= 0;
    }
}

class StateForm extends View.extend({
    regions: {
        header: {
            el: ".theader",
            replaceElement: true,
        },
        stateTable: {
            el: ".state-table",
            replaceElement: true,
        },
    },

    template: _.template(
        '<hr/><h4>State: <%= label %></h4>\n<table class="table"><thead class="theader"></thead><tbody class="state-table"></tbody></table>'
    ),
}) {
    onRender() {
        const options = this.options;
        const roleHeader = new RoleHeaderRow({
            collection: this.options.permissionsView.roleCollection,
            cell0: i18n.gettext("Permissions \\ Role"),
            parentView: this,
        });
        this.showChildView("header", roleHeader);
        const table = new StateRolePermissionTable({
            collection: options.permissionsView.permissionCollection,
            statePermissions: options.statePermissions,
            localPermissions: options.localPermissions,
            stateLabel: this.model.get("label"),
            permissionsView: options.permissionsView,
            parentView: this,
        });
        this.showChildView("stateTable", table);
    }
}

class StateList extends CollectionView.extend({
    childView: StateForm,
}) {
    childViewOptions(model) {
        const options = this.options;
        return {
            parentView: this,
            permissionsView: options.parentView,
            statePermissions: options.statePermissions,
            localPermissions: options.localPermissions,
        };
    }
}

/**
 * The new permissions window
 * @class app.views.admin.adminPermissions.PermissionsView
 */
class PermissionsView extends LoaderView.extend({
    template: "#tmpl-permissionsPanel",

    regions: {
        stateOptions: "#pub-state-options",
        header: {
            el: "#roles-header",
            replaceElement: true,
        },
        globalRows: {
            el: "#role-permissions-body",
            replaceElement: true,
        },
        //deleteRoleRow: '#delete-role-row',
        navigationMenuHolder: ".navigation-menu-holder",
        statesView: "#pubstate-permissions",
    },
}) {
    initialize() {
        this.setLoading(true);
        const that = this;
        const collectionManager = new CollectionManager();
        this.roleCollection = new RoleModels.roleCollection();
        this.permissionCollection = new RoleModels.permissionCollection();
        Promise.join(
            collectionManager.getIdeaPublicationStatesPromise(),
            collectionManager.getDiscussionAclPromise(),
            collectionManager.getPubStatePermissionsPromise()
        ).then(([ideaPubStates, discussionAcls, pubStatePermissions]) => {
            this.ideaPubStates = ideaPubStates;
            this.discussionAcls = discussionAcls;
            this.pubStatePermissions = pubStatePermissions;
            this.setLoading(false);
            this.render();
        });
    }

    onRender() {
        if (this.isLoading()) {
            return;
        }
        this.showChildView("navigationMenuHolder", this.getNavigationMenu());
        var roleHeader = new RoleHeaderRow({
            collection: this.roleCollection,
            cell0: i18n.gettext("Permissions \\ Role"),
            parentView: this,
        });
        this.showChildView("header", roleHeader);
        const globalPermissions = new RolePermissionTable({
            collection: this.permissionCollection,
            localPermissions: this.discussionAcls,
            parentView: this,
            permissionsView: this,
        });
        this.showChildView("globalRows", globalPermissions);
        const stateListView = new StateList({
            collection: this.ideaPubStates,
            localPermissions: this.discussionAcls,
            statePermissions: this.pubStatePermissions,
            parentView: this,
        });
        this.showChildView("statesView", stateListView);
    }

    canSavePermission(id) {
        var prefData = this.preferenceData[id];
        var neededPerm =
            prefData.modification_permission || Permissions.ADMIN_DISCUSSION;
        return Ctx.getCurrentUser().can(neededPerm);
    }

    getNavigationMenu() {
        return new AdminNavigationMenu.discussionAdminNavigationMenu({
            selectedSection: "permissions",
        });
    }
}

export default PermissionsView;
