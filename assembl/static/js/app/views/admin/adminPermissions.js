import Marionette from 'backbone.marionette';
import Promise from 'bluebird';
import _ from 'underscore';
import Growl from '../../utils/growl.js';

import i18n from '../../utils/i18n.js';
import Types from '../../utils/types.js';
import LoaderView from '../loaderView.js';
import CollectionManager from '../../common/collectionManager.js';
import AdminNavigationMenu from './adminNavigationMenu.js';
import RoleModels from '../../models/roles.js';

const RoleHeaderCell = Marionette.View.extend({
  constructor: function RoleHeaderCell() {
    Marionette.View.apply(this, arguments);
  },
  tagName: 'th',
  template: _.template("<%= name %>"),
});


const RoleHeaderRow = Marionette.CollectionView.extend({
  constructor: function RoleHeaderRow() {
    Marionette.CollectionView.apply(this, arguments);
  },
  _createBuffer() {
    // copied from Marionette... will be hard to keep up to date.
    // But I need the way to prefix an element in-place.
    const elBuffer = this.Dom.createBuffer();
    this.Dom.appendContents(elBuffer, "<th>"+this.options.cell0+"</th>");
    _.each(this._bufferedChildren, (b) => {
      this.Dom.appendContents(elBuffer, b.el, {_$contents: b.$el});
    });
    return elBuffer;
  },
  childViewOptions: function(model) {
    return {
      parentView: this
    };
  },
  childView: RoleHeaderCell,
  tagName: 'thead',
});


const RolePermissionCell = LoaderView.extend({
  constructor: function RolePermissionCell() {
    LoaderView.apply(this, arguments);
  },
  ui: {
    input: ".in",
  },
  events: {
    "click @ui.input": "onClick",
  },
  onClick: function(ev) {
    this.setLoading(true);
    this.render();
    if (ev.currentTarget.checked) {
      this.addPermission();
    } else {
      this.removePermission();
    }
  },
  addPermission: function() {
    const permission = new RoleModels.discPermModel({
      permission: this.options.permissionName,
      role: this.options.roleName,
      discussion: "local:"+Types.DISCUSSION+"/"+Ctx.getDiscussionId()
    });
    this.options.localPermissions.add(permission);
    permission.save({}, {
      success: () => {
        this.options.localPermission = permission;
        this.setLoading(false);
        this.render();
      },
      error: (model, resp) => {
        Growl.showBottomGrowl(Growl.GrowlReason.ERROR, i18n.gettext("Your settings failed to update."));
        this.setLoading(false);
        this.render();
      }
    });
  },
  removePermission: function() {
    this.options.localPermission.destroy({
      success: ()=>{
        this.options.localPermission = null;
        this.setLoading(false);
        this.render();
      },
      error: (model, resp) => {
        Growl.showBottomGrowl(Growl.GrowlReason.ERROR, i18n.gettext("Your settings failed to update."));
        this.setLoading(false);
        this.render();
      },
    });
  },
  serializeData: function() {
    return {
        checked: (this.options.localPermission) ? "checked='checked'" : '',
        disabled: '',
    }
  },
  tagName: "td",
  template: _.template("<input class='in' type='checkbox' <%= checked %> <%= disabled %>/>"),
});


const StateRolePermissionCell = RolePermissionCell.extend({
  constructor: function StateRolePermissionCell() {
    RolePermissionCell.apply(this, arguments);
  },
  serializeData: function() {
    return {
        checked: (this.options.statePermission || this.options.localPermission) ? "checked='checked'" : '',
        disabled: (this.options.localPermission) ? "disabled='disabled'" : '',
    }
  },
  addPermission: function() {
    const permission = new RoleModels.pubStatePermModel({
      permission: this.options.permissionName,
      role: this.options.roleName,
      state: this.options.stateLabel,
      discussion: "local:"+Types.DISCUSSION+"/"+Ctx.getDiscussionId()
    });
    this.options.statePermissions.add(permission);
    permission.save({}, {
      success: () => {
        this.options.statePermission = permission;
        this.setLoading(false);
        this.render();
      },
      error: (model, resp) => {
        Growl.showBottomGrowl(Growl.GrowlReason.ERROR, i18n.gettext("Your settings failed to update."));
        this.setLoading(false);
        this.render();
      }
    });
  },
  removePermission: function() {
    this.options.statePermission.destroy({
      success: ()=>{
        this.options.statePermission = null;
        this.setLoading(false);
        this.render();
      },
      error: (model, resp) => {
        Growl.showBottomGrowl(Growl.GrowlReason.ERROR, i18n.gettext("Your settings failed to update."));
        this.setLoading(false);
        this.render();
      },
    });
  },
});



const RolePermissionRow = Marionette.CollectionView.extend({
  constructor: function RolePermissionRow() {
    Marionette.CollectionView.apply(this, arguments);
  },
  childViewOptions: function(model) {
    const options = this.options;
    const roleName = model.get('name');
    const permissionName = options.model.get('name');
    const localPermission = options.localPermissions.find((lp) => {
        return lp.get('permission') == permissionName && lp.get('role') == roleName;
    });
    return {
      parentView: this,
      roleName: roleName,
      permissionName: permissionName,
      localPermissions: options.localPermissions,
      permissionsView: options.permissionsView,
      localPermission: localPermission,
    };
  },
  _createBuffer() {
    const elBuffer = this.Dom.createBuffer();
    this.Dom.appendContents(elBuffer, "<th>"+this.model.get('name')+"</th>");
    _.each(this._bufferedChildren, (b) => {
      this.Dom.appendContents(elBuffer, b.el, {_$contents: b.$el});
    });
    return elBuffer;
  },
  childView: RolePermissionCell,
  tagName: 'tr',
});


const StateRolePermissionRow = RolePermissionRow.extend({
  constructor: function StateRolePermissionRow() {
    RolePermissionRow.apply(this, arguments);
  },
  childViewOptions: function(model) {
    const options = this.options;
    const base = RolePermissionRow.prototype.childViewOptions.apply(this, arguments);
    const roleName = model.get('name');
    const permissionName = options.model.get('name');
    const statePermission = options.statePermissions.find((lp) => {
        return lp.get('permission') == permissionName && lp.get('role') == roleName &&
          lp.get('state') == options.stateLabel;
    });
    return _.extend(base, {
      stateLabel: options.stateLabel,
      statePermissions: options.statePermissions,
      statePermission: statePermission,
    });
  },
  childView: StateRolePermissionCell,
});


const DeleteRoleRow = RolePermissionRow.extend({
  constructor: function DeleteRoleRow() {
    RolePermissionRow.apply(this, arguments);
  },
});


const RolePermissionTable = Marionette.CollectionView.extend({
  constructor: function RolePermissionTable() {
    Marionette.CollectionView.apply(this, arguments);
  },
  childViewOptions: function(model) {
    const options = this.options;
    return {
      parentView: this,
      collection: options.permissionsView.roleCollection,
      localPermissions: options.localPermissions,
      permissionsView: options.permissionsView,
    };
  },
  childView: RolePermissionRow,
  tagName: 'tbody',
});


const StateRolePermissionTable = RolePermissionTable.extend({
  constructor: function StateRolePermissionTable() {
    RolePermissionTable.apply(this, arguments);
  },
  childViewOptions: function(model) {
    const options = this.options;
    const base = RolePermissionTable.prototype.childViewOptions.apply(this, arguments);
    return _.extend(base, {
      statePermissions: options.statePermissions,
      stateLabel: options.stateLabel,
    });
  },
  childView: StateRolePermissionRow,
  filter: function (child, index, collection) {
    return child.get('name').indexOf("Idea")>=0;
  },
});

const StateForm = Marionette.View.extend({
  constructor: function StateForm() {
    Marionette.View.apply(this, arguments);
  },
  regions: {
    header: {
      el: ".theader",
      replaceElement: true
    },
    stateTable: {
      el: ".state-table",
      replaceElement: true,
    },
  },
  onRender: function() {
    const options = this.options;
    const roleHeader = new RoleHeaderRow({
        collection: this.options.permissionsView.roleCollection,
        cell0: i18n.gettext('Permissions \\ Role'),
        parentView: this});
    this.showChildView("header", roleHeader);
    const table = new StateRolePermissionTable({
      collection: options.permissionsView.permissionCollection,
      statePermissions: options.statePermissions,
      localPermissions: options.localPermissions,
      stateLabel: this.model.get('label'),
      permissionsView: options.permissionsView,
      parentView: this,
    });
    this.showChildView("stateTable", table);
  },
  template: _.template('<hr/><h4>State: <%= label %></h4>\n<table class="table"><thead class="theader"></thead><tbody class="state-table"></tbody></table>'),
});


const StateList = Marionette.CollectionView.extend({
  constructor: function StateList() {
    Marionette.CollectionView.apply(this, arguments);
  },
  childViewOptions: function(model) {
    const options = this.options;
    return {
      parentView: this,
      permissionsView: options.parentView,
      statePermissions: options.statePermissions,
      localPermissions: options.localPermissions,
    };
  },
  childView: StateForm,
});


/**
 * The new permissions window
 * @class app.views.admin.adminPermissions.PermissionsView
 */
const PermissionsView = LoaderView.extend({
  constructor: function PermissionsView() {
    LoaderView.apply(this, arguments);
  },
  template: "#tmpl-permissionsPanel",
  regions: {
    stateOptions: "#pub-state-options",
    header: {
        el: "#roles-header",
        replaceElement: true,
    },
    globalRows: {
        el:"#role-permissions-body",
        replaceElement: true,
    },
    //deleteRoleRow: '#delete-role-row',
    navigationMenuHolder: ".navigation-menu-holder",
    statesView: "#pubstate-permissions",
  },
  initialize: function() {
    this.setLoading(true);
    const that = this;
    const collectionManager = new CollectionManager();
    this.roleCollection = new RoleModels.roleCollection();
    this.permissionCollection = new RoleModels.permissionCollection();
    Promise.join(
        collectionManager.getIdeaPublicationStatesPromise(),
        collectionManager.getDiscussionAclPromise(),
        collectionManager.getPubStatePermissionsPromise()
    ).then(([ideaPubStates, discussionAcls, pubStatePermissions])=>{
        this.ideaPubStates = ideaPubStates;
        this.discussionAcls = discussionAcls;
        this.pubStatePermissions = pubStatePermissions;
        this.setLoading(false);
        this.render();
    });
  },
  onRender: function() {
    if (this.isLoading()) {
        return;
    }
    this.showChildView("navigationMenuHolder", this.getNavigationMenu());
    var roleHeader = new RoleHeaderRow({
        collection: this.roleCollection,
        cell0: i18n.gettext('Permissions \\ Role'),
        parentView: this});
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
        parentView: this
    });
    this.showChildView("statesView", stateListView);
    
  },
  canSavePermission: function(id) {
    var prefData = this.preferenceData[id];
    var neededPerm = prefData.modification_permission || Permissions.ADMIN_DISCUSSION;
    return Ctx.getCurrentUser().can(neededPerm);
  },
  getNavigationMenu: function() {
    return new AdminNavigationMenu.discussionAdminNavigationMenu(
      {selectedSection: "permissions"});
  }
});

export default PermissionsView;
