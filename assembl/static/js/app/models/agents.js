/**
 * User profile and permissions (user or email author)
 * @module app.models.agents
 */
import $ from "jquery";
import Base from "./base.js";
import Ctx from "../common/context.js";
import i18n from "../utils/i18n.js";
import Promise from "bluebird";
import Permissions from "../utils/permissions.js";
import Roles from "../utils/roles.js";
var AVATAR_PLACEHOLDER = "//placehold.it/{0}";
var UNKNOWN_USER_ID = Roles.EVERYONE;

/**
 * Agent model
 * Frontend model for :py:class:`assembl.models.auth.AgentProfile`
 * @class app.models.agents.AgentModel
 * @extends app.models.base.BaseModel
 */
class AgentModel extends Base.Model.extend({
    /**
     * @member {string} app.models.agents.AgentModel.urlRoot
     */
    urlRoot: Ctx.getApiV2DiscussionUrl() + "all_users/",

    /**
     * Defaults
     * @type {Object}
     */
    defaults: {
        username: null,
        name: null,
        post_count: 0,
        preferred_email: null,
        verified: false,
        avatar_url_base: null,
        created: null,
        is_first_visit: false,
        first_visit: null,
        last_visit: null,
        last_login: null,
        real_name: null,
        accepted_tos_version: null,
        permissions: [],
        "@type": null,
        "@view": null,
    },

    /**
     * The list with all user's permissions
     * This is usefull only for the logged user.
     * @member {string[]} app.models.agents.AgentModel.permissions
     */
    permissions: [],
}) {
    /**
     * Load the permissions from script tag and populates `this.permissions`
     * @param {string} [id='permissions-json'] The script tag id
     * @function app.models.agents.AgentModel.fetchPermissionsFromScriptTag
     */
    fetchPermissionsFromScriptTag(id) {
        id = id || "permissions-json";
        try {
            this.permissions = Ctx.getJsonFromScriptTag(id);
        } catch (e) {
            throw new Error("Invalid json");
        }
    }

    /**
     * Load permissions from database
     * @function app.models.agents.AgentModel.fetchPermissions
     */
    fetchPermissions() {
        var that = this;
        var promise = Promise.resolve(
            $.get(Ctx.getApiUrl("permissions/u/" + this.getId()))
        );
        promise.then(function (permissions) {
            that.permissions = permissions;
        });
        return promise;
    }

    /**
     * return the avatar's url
     * @param  {number} [size=44] The avatar size
     * @returns {string}
     * @function app.models.agents.AgentModel.getAvatarUrl
     */
    getAvatarUrl(size) {
        var id = this.getId();
        return id != UNKNOWN_USER_ID
            ? Ctx.formatAvatarUrl(Ctx.extractId(id), size)
            : Ctx.format(AVATAR_PLACEHOLDER, size);
    }

    /**
     * Returns the avatar's color
     * @returns {string}
     * @function app.models.agents.AgentModel.getAvatarColor
     */
    getAvatarColor() {
        var numColors = 10;
        var hue = Math.round(
            (360.0 * (this.getNumericId() % numColors)) / numColors
        );
        return "hsl(" + hue + ", 60%, 65%)";
    }

    /**
     * Checks if user has permission
     * @param  {string}  permission The permission name
     * @returns {boolean} True if the user has the given permission
     * @function app.models.agents.AgentModel.hasPermission
     */
    hasPermission(permission) {
        return $.inArray(permission, this.permissions) >= 0;
    }

    /**
     * @alias hasPermission
     * @param {String} permission
     * @returns {Boolean}
     * @function app.models.agents.AgentModel.can
     */
    can(permission) {
        return this.hasPermission(permission);
    }

    /**
     * A text message designed to replace X in the question "You cannot perform this operation because X"
     * @param {String?} permission
     * @param {Number?} discussion
     * @param {String?} reroute_relative_url
     * @returns {string}
     * @function app.models.agents.AgentModel.getRolesMissingMessageForPermission
     */
    getRolesMissingMessageForPermission(
        permission,
        discussion,
        reroute_relative_url
    ) {
        if (this.hasPermission(permission)) {
            return i18n.gettext("need no additional permissions");
        } else if (this.isUnknownUser()) {
            var url;
            if (reroute_relative_url) {
                url = Ctx.appendExtraURLParams(Ctx.getLoginURL(), {
                    next: reroute_relative_url,
                });
            } else {
                url = Ctx.getLoginURL();
            }
            return i18n.sprintf(
                i18n.gettext("you must first <a href='%s'>Sign in</a>"),
                url
            );
        } else if (discussion !== undefined) {
            var rolesGrantingPermission = discussion.getRolesForPermission(
                permission
            );
            if (_.size(rolesGrantingPermission) > 0) {
                if (
                    _.contains(rolesGrantingPermission, Roles.PARTICIPANT) &&
                    _.contains(
                        discussion.getRolesForPermission(
                            Permissions.SELF_REGISTER
                        ),
                        Roles.AUTHENTICATED
                    )
                ) {
                    return i18n.sprintf(
                        i18n.gettext("you must first join this discussion")
                    );
                } else {
                    // TODO:  Handle the case of self_register_req
                    // TODO: linguistic version of roles.
                    return i18n.sprintf(
                        i18n.ngettext(
                            "you must ask a discussion administrator for the following role: %s",
                            "you must ask a discussion administrator for one of the following roles: %s",
                            _.size(rolesGrantingPermission)
                        ),
                        rolesGrantingPermission.join(", ")
                    );
                }
            } else {
                return i18n.gettext(
                    "the administrator has closed this discussion to all contributions"
                );
            }
        } else {
            return i18n.gettext("you need additional permissions");
        }
    }

    /**
     * Returns true if the user is an unknown user
     * @returns {Boolean}
     * @function app.models.agents.AgentModel.isUnknownUser
     */
    isUnknownUser() {
        return this.getId() === UNKNOWN_USER_ID || this.getId() === undefined;
    }

    /**
     * Validate the model attributes
     * @function app.models.agents.AgentModel.validate
     */
    validate(attrs, options) {
        /**
         * check typeof variable
         * */
    }
}

/**
 * Agents collection
 * @class app.models.agents.AgentCollection
 * @extends app.models.base.BaseCollection
 */
class AgentCollection extends Base.Collection.extend({
    /**
     * @member {string} app.models.agents.AgentCollection.url
     */
    url: Ctx.getApiUrl("agents/"),

    /**
     * The model
     * @member {AgentModel} app.models.agents.AgentCollection.model
     */
    model: AgentModel,
}) {
    /**
     * Returns the user by his/her id, or return the unknown user
     * @param {Number} id
     * @returns {Object}
     * @function app.models.agents.AgentCollection.getById
     */
    getById(id) {
        var user = this.get(id);
        return user || this.getUnknownUser();
    }

    /**
     * Returns the unknown user object
     * @returns {Object}
     * @function app.models.agents.AgentCollection.getUnknownUser
     */
    getUnknownUser() {
        return UNKNOWN_USER;
    }
}

/**
 * The unknown User
 * @type {UserModel}
 */
var UNKNOWN_USER = new AgentModel({
    "@id": UNKNOWN_USER_ID,
    name: i18n.gettext("Unknown user"),
});

export default {
    Model: AgentModel,
    Collection: AgentCollection,
};
