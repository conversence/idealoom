/**
 * A role that the user is granted in this discussion
 * @module app.models.roles
 */

import Base from './base.js';

import Ctx from '../common/context.js';
import Roles from '../utils/roles.js';
import Permissions from '../utils/permissions.js';
import Types from '../utils/types.js';
import Analytics from '../internal_modules/analytics/dispatcher.js';


/**
 * Role model
 * Frontend model for :py:class:`assembl.models.permissions.Role`
 * @class app.models.roles.RoleModel
 * @extends app.models.base.BaseModel
 */
var RoleModel = Base.Model.extend({
  constructor: function RoleModel() {
    Base.Model.apply(this, arguments);
  },

  urlRoot: Ctx.getApiV2Url("/roles"),

  defaults: {
    '@id': null,
    '@type': null,
    '@view': null
  },
});

/**
 * LocalRoles collection
 * @class app.models.roles.localRoleCollection
 * @extends app.models.base.BaseCollection
 */
var RoleCollection = Base.Collection.extend({
  constructor: function RoleCollection() {
    Base.Collection.apply(this, arguments);
    var roles = Ctx.getJsonFromScriptTag('role-names')
    roles = _.sortBy(roles);
    _.map(roles, (v)=>{
      this.add(new RoleModel({'@id': v, name: v}));
    });
  },

  url: Ctx.getApiV2Url("/roles"),
  model: RoleModel,
});





/**
 * Role model
 * Frontend model for :py:class:`assembl.models.permissions.Permission`
 * @class app.models.roles.PermissionModel
 * @extends app.models.base.BaseModel
 */
var PermissionModel = Base.Model.extend({
  constructor: function PermissionModel() {
    Base.Model.apply(this, arguments);
  },

  urlRoot: Ctx.getApiV2Url("/permissions"),

  defaults: {
    '@id': null,
    '@type': null,
    '@view': null
  },
});

/**
 * LocalPermissions collection
 * @class app.models.roles.localPermissionCollection
 * @extends app.models.base.BaseCollection
 */
var PermissionCollection = Base.Collection.extend({
  constructor: function PermissionCollection() {
    Base.Collection.apply(this, arguments);
    var permissions = _.values(Permissions);
    permissions = _.sortBy(permissions);
    _.map(permissions, (v)=>{
      this.add(new PermissionModel({'@id': v, name: v}));
    });
  },

  url: Ctx.getApiV2Url("/permissions"),
  model: PermissionModel,
});


/**
 * LocalRole model
 * Frontend model for :py:class:`assembl.models.permissions.LocalUserRole`
 * @class app.models.roles.localRoleModel
 * @extends app.models.base.BaseModel
 */
var localRoleModel = Base.Model.extend({
  constructor: function localRoleModel() {
    Base.Model.apply(this, arguments);
  },

  urlRoot: Ctx.getApiV2Url(Types.LOCAL_ROLE),

  defaults: {
    'requested': false,
    'discussion': null,
    'role': null,
    'user': null,
    '@id': null,
    '@type': null,
    '@view': null
  },

  validate: function(attrs, options) {
    /**
     * check typeof variable
     * */
  }

});

/**
 * LocalRoles collection
 * @class app.models.roles.localRoleCollection
 * @extends app.models.base.BaseCollection
 */
var localRoleCollection = Base.Collection.extend({
  constructor: function myLocalRoleCollection() {
    Base.Collection.apply(this, arguments);
  },
  url: Ctx.getApiV2Url(Types.LOCAL_ROLE),
  model: localRoleModel,
})

/**
 * MyLocalRoles collection
 * @class app.models.roles.myLocalRoleCollection
 * @extends app.models.base.BaseCollection
 */
var myLocalRoleCollection = localRoleCollection.extend({
  constructor: function myLocalRoleCollection() {
    localRoleCollection.apply(this, arguments);
  },

  url: function() {
    if (Ctx.isAdminApp()) {
      return Ctx.getApiV2Url("/"+Types.USER+"/"+Ctx.getCurrentUserId()+"/roles")
    } else {
      return Ctx.getApiV2DiscussionUrl("/all_users/current/local_roles")
    }
  },

  /** This method needs to change once subscription has it's own table 
   *
   */
  isUserSubscribedToDiscussion: function() {
    //console.log("isUserSubscribedToDiscussion returning", this.hasRole(Roles.PARTICIPANT))
    return this.hasRole(Roles.PARTICIPANT);
  },

  /**
   * @param  {Role}  The role
   * @returns {boolean} True if the user has the given role
   */
  hasRole: function(role) {
    var roleFound =  this.find(function(local_role) {
      return local_role.get('role') === role;
    });
    return roleFound !== undefined;
  },

  UnsubscribeUserFromDiscussion: function() {
    var that = this;

    var role =  this.find(function(local_role) {
      return local_role.get('role') === Roles.PARTICIPANT;
    });

    role.destroy({
      success: function(model, resp) {
        that.remove(model);
        var analytics = Analytics.getInstance();
        analytics.trackEvent(analytics.events.LEAVE_DISCUSSION);
      },
      error: function(model, resp) {
        console.error('ERROR: unSubscription failed', resp);
      }});
  }
});



/**
 * DiscussionPermission model
 * Frontend model for :py:class:`assembl.models.permissions.DiscussionPermission`
 * @class app.models.permission.discussionPermissionModel
 * @extends app.models.base.BaseModel
 */

var discussionPermissionModel = Base.Model.extend({
  constructor: function discussionPermissionModel() {
    Base.Model.apply(this, arguments);
  },

  urlRoot: Ctx.getApiV2DiscussionUrl("/acls"),

  defaults: {
    'discussion': null,
    'role': null,
    'permission': null,
    '@id': null,
    '@type': null,
    '@view': null
  },

  validate: function(attrs, options) {
    /**
     * check typeof variable
     * */
  }

});

/**
 * DiscussionPermission collection
 * @class app.models.roles.discussionPermissionCollection
 * @extends app.models.base.BaseCollection
 */

var discussionPermissionCollection = Base.Collection.extend({
  constructor: function discussionPermissionCollection() {
    Base.Collection.apply(this, arguments);
  },

  url: Ctx.getApiV2DiscussionUrl("/acls"),
  model: discussionPermissionModel,
});


/**
 * StatePermission model
 * Frontend model for :py:class:`assembl.models.publication_states.StateDiscussionPermission`
 * @class app.models.permission.pubStatePermissionModel
 * @extends app.models.base.BaseModel
 */

var pubStatePermissionModel = Base.Model.extend({
  constructor: function pubStatePermissionModel() {
    Base.Model.apply(this, arguments);
  },

  urlRoot: Ctx.getApiV2DiscussionUrl("/publication_permissions"),

  defaults: {
    'discussion': null,
    'role': null,
    'publication_state': null,
    'permission': null,
    '@id': null,
    '@type': null,
    '@view': null
  },

  validate: function(attrs, options) {
    /**
     * check typeof variable
     * */
  }

});

/**
 * StatePermission collection
 * @class app.models.roles.pubStatePermissionCollection
 * @extends app.models.base.BaseCollection
 */

var pubStatePermissionCollection = Base.Collection.extend({
  constructor: function pubStatePermissionCollection() {
    Base.Collection.apply(this, arguments);
  },

  url: Ctx.getApiV2DiscussionUrl("/publication_permissions"),
  model: pubStatePermissionModel,
});


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
