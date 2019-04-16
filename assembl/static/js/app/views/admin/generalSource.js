/**
 * 
 * @module app.views.admin.generalSource
 */
import Marionette from 'backbone.marionette';
import $ from 'jquery';
import _ from 'underscore';
import Moment from 'moment';

import i18n from '../../utils/i18n.js';
import Types from '../../utils/types.js';
import Ctx from '../../common/context.js';
import Permissions from '../../utils/permissions.js';
import Growl from '../../utils/growl.js';
import Source from '../../models/sources.js';
import CollectionManager from '../../common/collectionManager.js';
import getSourceEditView from './sourceEditViews.js';


class ReadSource extends Marionette.View.extend({
  template: '#tmpl-adminImportSettingsGeneralSourceRead',

  ui: {
      manualStart: '.js_manualStart',
      reimport: '.js_reimport',
      reprocess: '.js_reprocess',
      showEdit: '.js_moreOptions',
  },

  modelEvents: {
      'change': 'updateView'
  },

  events: {
      'click @ui.manualStart': 'manualStart',
      'click @ui.reimport': 'reimportSource',
      'click @ui.reprocess': 'reprocessSource',
      'click @ui.showEdit': 'toggleEditView'
  }
}) {
  initialize(options) {
      this.parent = options.parent;
      this.model = this.parent.model;
  }

  toggleEditView() {
      this.parent.toggleEditView();
  }

  reimportSource(e) {
      e.preventDefault();
      e.stopPropagation();
      return Promise.resolve(this.model.doReimport()).then(function(resp) {
          if (_.has(resp, 'error')){
              Growl.showBottomGrowl(Growl.GrowlReason.ERROR, i18n.gettext("There was a reimport error!"));
              console.error("Source " + this.model.name + " failed to reimport due to an internal server problem with response ", resp);
          }
          Growl.showBottomGrowl(Growl.GrowlReason.SUCCESS, i18n.gettext('Reimport has begun! It can take up to 15 minutes to complete.'));
      }).catch(function(e) {
          Growl.showBottomGrowl(Growl.GrowlReason.ERROR, i18n.gettext('Reimport failed.'));
      });
  }

  reprocessSource(e) {
      e.preventDefault();
      e.stopPropagation();
      return Promise.resolve(this.model.doReprocess()).then(function(resp) {
          if (_.has(resp, 'error')){
              Growl.showBottomGrowl(Growl.GrowlReason.ERROR, i18n.gettext("There was a reprocess error!"));
              console.error("Source " + this.model.name + " failed to reprocess due to an internal server problem with response", resp);
          }
          Growl.showBottomGrowl(Growl.GrowlReason.SUCCESS, i18n.gettext('Reprocess has begun! It can take up to 15 minutes to complete.'));
      }).catch(function(e) {
          Growl.showBottomGrowl(Growl.GrowlReason.ERROR, i18n.gettext('Reprocess failed'));
      });
  }

  manualStart(evt) {
    var url = this.model.url() + "/fetch_posts";
    var user = Ctx.getCurrentUser();
    var payload = {};
    if (user.can(Permissions.ADMIN_DISCUSSION)){
      payload.force_restart = true;
    }
    $.ajax(
      url,
      {
        method: "POST",
        contentType: "application/json; charset=UTF-8",
        data: JSON.stringify(payload)
      }
    ).then(function() {
      Growl.showBottomGrowl(Growl.GrowlReason.SUCCESS, i18n.gettext('Import has begun!'))
    });
  }

  serializeData() {
    // TODO: Name for the types
    var backoff = this.model.get('error_backoff_until');
    return {
      name: this.model.get('name'),
      type: this.model.localizedName,
      connection_error: this.model.get('connection_error') || '',
      error_desc: this.model.get('error_description') || '',
      error_backoff: backoff ? Moment(backoff).fromNow() : '',
    };
  }

  updateView(evt) {
      this.render(); //Update 
  }
}

function getSourceDisplayView(model) {
  // TODO
  return ReadSource;
}


class SourceView extends Marionette.View.extend({
  ui: {
    edit_container: '.js_source_edit_container'
  },

  template: '#tmpl-adminImportSettingsGeneralSource',

  regions: {
    readOnly: '.js_source_read',
    form: '.js_source_edit'
  }
}) {
  toggleEditView() {
    this.ui.edit_container.toggleClass('hidden');
  }

  onRender() {
    var display_view = getSourceDisplayView(this.model);
    this.showChildView('readOnly', new display_view({parent: this}));
    var editViewClass = getSourceEditView(this.model.get("@type"));
    if (editViewClass !== undefined) {
      this.showChildView('form', new editViewClass({model: this.model}));
    }
  }
}

class CreateSource extends Marionette.View.extend({
  template: '#tmpl-DiscussionSettingsCreateSource',

  regions: {
    edit_form: ".js_editform"
  },

  ui: {
    selector: ".js_contentSourceType",
    create_button: ".js_contentSourceCreate",
  },

  events: {
    'click @ui.create_button': 'createButton',
    'change @ui.selector': 'changeSubForm',
  },

  editView: undefined
}) {
  serializeData() {
    var types = [
        Types.IMAPMAILBOX,
        Types.MAILING_LIST,
        Types.FEED_POST_SOURCE,
        Types.LOOMIO_POST_SOURCE,
        Types.IDEALOOM_IDEA_SOURCE,
        Types.CATALYST_IDEA_SOURCE,
        Types.HYPOTHESIS_EXTRACT_SOURCE,
        Types.FACEBOOK_GROUP_SOURCE,
        Types.FACEBOOK_GROUP_SOURCE_FROM_USER,
        Types.FACEBOOK_PAGE_POSTS_SOURCE,
        Types.FACEBOOK_PAGE_FEED_SOURCE,
        Types.FACEBOOK_SINGLE_POST_SOURCE
      ];

    var type_name_assoc = {};
    for (var i in types) {
      type_name_assoc[types[i]] = Source.getSourceClassByType(types[i]).prototype.localizedName;
    }
    return {
      types: types,
      type_names: type_name_assoc
    };
  }

  changeSubForm(ev) {
    var sourceType = ev.currentTarget.value;
    var editViewClass = getSourceEditView(sourceType);
    var modelClass = Source.getSourceClassByType(sourceType);
    if (editViewClass !== undefined && modelClass !== undefined) {
      this.editView = new editViewClass({model: new modelClass()});
      this.showChildView('edit_form', this.editView);
    } else {
      this.editView = undefined;
      this.showChildView('edit_form', "");
    }
  }

  createButton(ev) {
    if (this.editView !== undefined) {
      this.editView.saveModel();
    }
  }
}

class DiscussionSourceList extends Marionette.CollectionView.extend({
  // getChildView: getSourceDisplayView
  childView: SourceView
}) {}


export default {
    Item: ReadSource,
    Root: SourceView,
    CreateSource: CreateSource,
    DiscussionSourceList: DiscussionSourceList
}
