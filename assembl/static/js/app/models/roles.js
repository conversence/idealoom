/**
 * A role that the user is granted in this discussion
 * @module app.models.roles
 */

import Base from "./base.js";

import Ctx from "../common/context.js";
import Roles from "../utils/roles.js";
import Permissions from "../utils/permissions.js";
import Types from "../utils/types.js";
import Analytics from "../internal_modules/analytics/dispatcher.js";

/**
 * Role model
 * Frontend model for :py:class:`assembl.models.permissions.Role`
 * @class app.models.roles.RoleModel
 * @extends app.models.base.BaseModel
 */
class RoleModel extends Base.Model.extend({
    urlRoot: Ctx.getApiV2Url("/roles"),

    defaults: {
        "@id": null,
        "@type": null,
        "@view": null,
    },
}) {}

/**
 * LocalRoles collection
 * @class app.models.roles.localRoleCollection
 * @extends app.models.base.BaseCollection
 */
class RoleCollection extends Base.Collection.extend({
    url: Ctx.getApiV2Url("/roles"),
    model: RoleModel,
}) {
    constructor() {
        super(...arguments);
        var roles = Ctx.getJsonFromScriptTag("role-names");
        roles = _.sortBy(roles);
        _.map(roles, (v) => {
            this.add(new RoleModel({ "@id": v, name: v }));
        });
    }
}

/**
 * Role model
 * Frontend model for :py:class:`assembl.models.permissions.Permission`
 * @class app.models.roles.PermissionModel
 * @extends app.models.base.BaseModel
 */
class PermissionModel extends Base.Model.extend({
    urlRoot: Ctx.getApiV2Url("/permissions"),

    defaults: {
        "@id": null,
        "@type": null,
        "@view": null,
    },
}) {}

/**
 * LocalPermissions collection
 * @class app.models.roles.localPermissionCollection
 * @extends app.models.base.BaseCollection
 */
class PermissionCollection extends Base.Collection.extend({
    url: Ctx.getApiV2Url("/permissions"),
    model: PermissionModel,
}) {
    constructor() {
        super(...arguments);
        var permissions = _.values(Permissions);
        permissions = _.sortBy(permissions);
        _.map(permissions, (v) => {
            this.add(new PermissionModel({ "@id": v, name: v }));
        });
    }
}

/**
 * LocalRole model
 * Frontend model for :py:class:`assembl.models.permissions.LocalUserRole`
 * @class app.models.roles.localRoleModel
 * @extends app.models.base.BaseModel
 */
class localRoleModel extends Base.Model.extend({
    urlRoot: Ctx.getApiV2DiscussionUrl("local_user_roles"),

    defaults: {
        requested: false,
        discussion: null,
        role: null,
        user: null,
        "@id": null,
        "@type": null,
        "@view": null,
    },
}) {
    validate(attrs, options) {
        /**
         * check typeof variable
         * */
    }
}

/**
 * LocalRoles collection
 * @class app.models.roles.localRoleCollection
 * @extends app.models.base.BaseCollection
 */
class localRoleCollection extends Base.Collection.extend({
    url: Ctx.getApiV2DiscussionUrl("local_user_roles"),
    model: localRoleModel,
}) {}

/**
 * MyLocalRoles collection
 * @class app.models.roles.myLocalRoleCollection
 * @extends app.models.base.BaseCollection
 */
class myLocalRoleCollection extends localRoleCollection {
    url() {
        if (Ctx.isAdminApp()) {
            return Ctx.getApiV2Url(
                "/" + Types.USER + "/" + Ctx.getCurrentUserId() + "/roles"
            );
        } else {
            return Ctx.getApiV2DiscussionUrl("/all_users/current/local_roles");
        }
    }

    /** This method needs to change once subscription has it's own table
     *
     */
    isUserSubscribedToDiscussion() {
        //console.log("isUserSubscribedToDiscussion returning", this.hasRole(Roles.PARTICIPANT))
        return this.hasRole(Roles.PARTICIPANT);
    }

    /**
     * @param  {Role}  The role
     * @returns {boolean} True if the user has the given role
     */
    hasRole(role) {
        var roleFound = this.find(function (local_role) {
            return local_role.get("role") === role;
        });
        return roleFound !== undefined;
    }

    UnsubscribeUserFromDiscussion() {
        var that = this;

        var role = this.find(function (local_role) {
            return local_role.get("role") === Roles.PARTICIPANT;
        });

        role.destroy({
            success: function (model, resp) {
                that.remove(model);
                var analytics = Analytics.getInstance();
                analytics.trackEvent(analytics.events.LEAVE_DISCUSSION);
            },
            error: function (model, resp) {
                console.error("ERROR: unSubscription failed", resp);
            },
        });
    }
}

/**
 * DiscussionPermission model
 * Frontend model for :py:class:`assembl.models.permissions.DiscussionPermission`
 * @class app.models.permission.discussionPermissionModel
 * @extends app.models.base.BaseModel
 */

class discussionPermissionModel extends Base.Model.extend({
    urlRoot: Ctx.getApiV2DiscussionUrl("/acls"),

    defaults: {
        discussion: null,
        role: null,
        permission: null,
        "@id": null,
        "@type": null,
        "@view": null,
    },
}) {
    validate(attrs, options) {
        /**
         * check typeof variable
         * */
    }
}

/**
 * DiscussionPermission collection
 * @class app.models.roles.discussionPermissionCollection
 * @extends app.models.base.BaseCollection
 */

class discussionPermissionCollection extends Base.Collection.extend({
    url: Ctx.getApiV2DiscussionUrl("/acls"),
    model: discussionPermissionModel,
}) {}

/**
 * StatePermission model
 * Frontend model for :py:class:`assembl.models.publication_states.StateDiscussionPermission`
 * @class app.models.permission.pubStatePermissionModel
 * @extends app.models.base.BaseModel
 */

class pubStatePermissionModel extends Base.Model.extend({
    urlRoot: Ctx.getApiV2DiscussionUrl("/publication_permissions"),

    defaults: {
        discussion: null,
        role: null,
        publication_state: null,
        permission: null,
        "@id": null,
        "@type": null,
        "@view": null,
    },
}) {
    validate(attrs, options) {
        /**
         * check typeof variable
         * */
    }
}

/**
 * StatePermission collection
 * @class app.models.roles.pubStatePermissionCollection
 * @extends app.models.base.BaseCollection
 */

class pubStatePermissionCollection extends Base.Collection.extend({
    url: Ctx.getApiV2DiscussionUrl("/publication_permissions"),
    model: pubStatePermissionModel,
}) {}

export default {
    roleModel: RoleModel,
    roleCollection: RoleCollection,
    permissionModel: PermissionModel,
    permissionCollection: PermissionCollection,
    localRoleModel: localRoleModel,
    localRoleCollection: localRoleCollection,
    myLocalRoleCollection: myLocalRoleCollection,
    discPermModel: discussionPermissionModel,
    discPermCollection: discussionPermissionCollection,
    pubStatePermModel: pubStatePermissionModel,
    pubStatePermCollection: pubStatePermissionCollection,
};
