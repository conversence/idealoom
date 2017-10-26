/**
 *
 * @module app.views.reusableDataFields.EditableLSField
 */

var Marionette = require('backbone.marionette');

var _ = require('underscore');
var $ = require('jquery');
var Assembl = require('../../app.js');
var Permissions = require('../../utils/permissions.js');
var LangString = require('../../models/langstring.js');
var CK = require('ckeditor');
var EditableField = require('./editableField.js');
var Ctx = require('../../common/context.js');



var EditableLSField = EditableField.extend({
  constructor: function EditableLSField() {
    EditableField.apply(this, arguments);
  },

  /**
   * CkLSeditor default configuration
   * @type {object}
   */

  initialize: function(options) {
    if (this.model === null) {
      throw new Error('EditableField needs a model');
    }
    if (this.translationData === null) {
      // Or just current Ctx.getLocale()?
      throw new Error('EditableField needs translationData');
    }
    this.translationData = options.translationData;
    EditableField.prototype.initialize.apply(this, arguments)
  },

  getTextValue: function() {
    var ls = this.model.get(this.modelProp);
    if (!ls) {
      return '';
    }
    if (this.editing) {
      // use interface value for edition
      return ls.forInterfaceValue() || '';
    }
    return ls.bestValue(this.translationData);
  },

  setTextValue: function(text) {
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
        '@language': Ctx.getLocale(),
      });
      ls.get("entries").add(lse);
    } else {
      lse.set('value', text);
    }
    attrs[this.modelProp] = ls;
    this.model.save(attrs, {
      success: function(model, resp) {},
      error: function(model, resp) {
        console.error('ERROR: saveEdition', resp.responseJSON);
      },
    });
  },
});

module.exports = EditableLSField;
