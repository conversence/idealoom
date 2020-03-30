/**
 *
 * @module app.views.reusableDataFields.ckeditorLSField
 */

import Marionette from 'backbone.marionette';

import _ from 'underscore';
import $ from 'jquery';
import IdeaLoom from '../../app.js';
import Permissions from '../../utils/permissions.js';
import LangString from '../../models/langstring.js';
import CK from 'ckeditor';
import CKEditorField from './ckeditorField.js';
import Ctx from '../../common/context.js';



class cKEditorLSField extends CKEditorField {
  /**
   * CkLSeditor default configuration
   * @type {object}
   */

  initialize(options) {
    if (this.model === null) {
      throw new Error('EditableField needs a model');
    }
    if (this.translationData === null) {
      // Or just current Ctx.getLocale()?
      throw new Error('EditableField needs translationData');
    }
    this.translationData = options.translationData;
    super.initialize(...arguments);
  }

  getTextValue() {
    var ls = this.model.get(this.modelProp);
    if (!ls) {
      return '';
    }
    if (this.editing) {
      // use interface value for edition
      return ls.forInterfaceValue() || '';
    }
    return ls.bestValue(this.translationData);
  }

  setTextValue(text) {
    var lse;
    var attrs = {};
    var ls = this.model.get(this.modelProp);
    if (!ls) {
      ls = new LangString.Model();
      ls.initFromDict({});
    }
    lse = ls.forInterface();
    if (!lse) {
      lse = new LangString.EntryModel({
        value: text,
        '@language': Ctx.getLocale()
      });
      ls.get("entries").add(lse);
    } else {
      lse.set('value', text);
      lse.set('@language', Ctx.getLocale()); // i.e. clear translation status
      lse.set('error_code', undefined);
    }
    attrs[this.modelProp] = ls;
    this.model.save(attrs, {
      success: function(model, resp) {},
      error: function(model, resp) {
        console.error('ERROR: saveEdition', resp.responseJSON);
      },
    });
  }

  createModal() {
    return new CkeditorLSFieldInModal({model:this.model, modelProp:this.modelProp, canEdit:this.canEdit, translationData: this.translationData});
  }
}

class CkeditorLSFieldInModal extends CKEditorField.modalClass {
  initialize(options) {
    this.model = options.model;
    this.modelProp = options.modelProp;
    this.canEdit = options.canEdit;
    this.autosave = options.autosave;
    this.translationData = options.translationData;
  }

  serializeData() {
    // this assumes the model is an idea, which should now be another case.
    // Probably used for other objects like announcements.
    // REVISIT. Probably use a substring of getTextValue.
    return {
      modal_title: this.model.getShortTitleSafe(this.translationData),
    };
  }

  onRender() {
    var ckeditorField = new cKEditorLSField({
      model: this.model,
      modelProp: this.modelProp,
      canEdit: this.canEdit,
      autosave: this.autosave,
      translationData: this.translationData,
      hideSeeMoreButton: true
    });
    this.$(this.ui.body).html(ckeditorField.render().el);
  }
}


export default cKEditorLSField;
