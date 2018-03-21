/**
 * 
 * @module app.views.reusableDataFields.ckeditorField
 */

import Marionette from 'backbone.marionette';

import _ from 'underscore';
import $ from 'jquery';
import dotdotdot from 'jquery.dotdotdot';
import IdeaLoom from '../../app.js';
import Backbone from 'backbone';
import BackboneModal from 'backbone.modal';
import Permissions from '../../utils/permissions.js';
import CK from 'ckeditor';
import Ctx from '../../common/context.js';


var cKEditorField = Marionette.View.extend({
  constructor: function cKEditorField() {
    Marionette.View.apply(this, arguments);
  },

  template: '#tmpl-ckeditorField',
  /**
   * Ckeditor default configuration
   * For complete reference see:
   * http://docs.ckeditor.com/#!/api/CKEDITOR.config
   * @type {object}
   */
  CKEDITOR_CONFIG: {
    toolbar: [
        ['Bold', 'Italic', 'Outdent', 'Indent', 'NumberedList', 'BulletedList'],
        ['Link', 'Unlink', 'Anchor']
    ],
    extraPlugins: 'sharedspace',
    removePlugins: 'floatingspace,resize',
    sharedSpaces: { top: 'ckeditor-toptoolbar', bottom: 'ckeditor-bottomtoolbar' },
    disableNativeSpellChecker: false,
    language: Ctx.getLocale(),
    title: false //Removes the annoying tooltip in the middle of the main textarea
  },

  ckInstance: null,

  showPlaceholderOnEditIfEmpty: false,

  initialize: function(options) {

    if (this.model === null) {
      throw new Error('EditableField needs a model');
    }
    //console.log("cKEditorField options: ", options);

    this.view = this;

    this.topId = _.uniqueId('ckeditorField-topid');
    this.fieldId = _.uniqueId('ckeditorField');
    this.bottomId = _.uniqueId('ckeditorField-bottomid');

    this.openInModal = (options.openInModal) ? options.openInModal : false;

    this.autosave = (options.autosave) ? options.autosave : false;

    this.hideButton = (options.hideButton) ? options.hideButton : false;

    this.editing = (this.editing) ? true : false;

    this.modelProp = (options.modelProp) ? options.modelProp : null;

    this.placeholder = (options.placeholder) ? options.placeholder : null;

    this.showPlaceholderOnEditIfEmpty = (options.showPlaceholderOnEditIfEmpty) ? options.showPlaceholderOnEditIfEmpty : null;

    this.canEdit = (options.canEdit !== undefined) ? options.canEdit : true;

    this.readMoreAfterHeightPx = (options.readMoreAfterHeightPx !== undefined) ? options.readMoreAfterHeightPx : 170;

    this.hideSeeMoreButton = (options.hideSeeMoreButton) ? options.hideSeeMoreButton : false;

    this.listenTo(this.model, 'add remove change', this.render);
  },

  ui: {
    mainfield: '.ckeditorField-mainfield',
    saveButton: '.ckeditorField-savebtn',
    cancelButton: '.ckeditorField-cancelbtn',
    seeMoreOrLess: '.js_seeMoreOrLess',
    seeMore: '.js_seeMore',
    seeLess: '.js_seeLess'
  },

  events: {
    'click @ui.mainfield': 'changeToEditMode',
    'click @ui.saveButton': 'saveEdition',
    'click @ui.cancelButton': 'cancelEdition',
    'click @ui.seeMore': 'seeMoreContent',
    'click @ui.seeLess': 'seeLessContent'
  },

  getTextValue: function() {
    return this.model.get(this.modelProp);
  },

  setTextValue: function(text) {
    this.model.save(this.modelProp, text, {
      success: function(model, resp) {},
      error: function(model, resp) {
        console.error('ERROR: saveEdition', resp.responseJSON);
      }
    });
  },

  serializeData: function() {
    var text = this.getTextValue();
    var textToShow = (this.showPlaceholderOnEditIfEmpty && !text) ? this.placeholder : text;

    return {
      topId: this.topId,
      fieldId: this.fieldId,
      bottomId: this.bottomId,
      text: textToShow,
      editing: this.editing,
      canEdit: this.canEdit,
      placeholder: this.placeholder,
      hideButton: this.hideButton,
    };
  },

  onRender: function() {
    this.destroy();
    if (this.editing) {
      this.startEditing();
    }
    if (this._viewIsAlreadyShown) {
      this.requestEllipsis();
    }
    if(this.hideSeeMoreButton){
      this.$(this.ui.seeMore).hide();
    }
  },

  onAttach: function() {
    this.requestEllipsis();
    this._viewIsAlreadyShown = true;
  },

  onDetach: function() {
    this.destroy();
    this._viewIsAlreadyShown = false;
  },

  onDomRemove: function() {
    if (this._viewIsAlreadyShown) {
      // onDetach seems not to happen?
      this.onDetach();
    }
  },

  requestEllipsis: function() {
    var that = this;
    setTimeout(function() {
      that.ellipsis(that.ui.mainfield, that.ui.seeMore);
    }, 0);
  },

  ellipsis: function(sectionSelector, seemoreUi) {
    /* We use https://github.com/MilesOkeefe/jQuery.dotdotdot to show
     * Read More links for introduction preview
     */
    var that = this;
    sectionSelector.dotdotdot({
      after: seemoreUi,
      height: that.readMoreAfterHeightPx,
      callback: function(isTruncated, orgContent) {

        if (isTruncated) {
          that.ui.seeMore.removeClass('hidden');
        }
        else {
          that.ui.seeMore.addClass('hidden');
        }
      },
      watch: "window"
    });

  },

  seeMoreContent: function(e) {
    e.stopPropagation();
    e.preventDefault();
    if(!this.openInModal){
      this.ui.mainfield.trigger('destroy');
      this.ui.seeMore.addClass('hidden');
      this.ui.seeLess.removeClass('hidden');
    }else{
      //Open ckeditor in modal when click on seeMore button
      var modalView = this.createModal();
      IdeaLoom.rootView.showChildView('slider', modalView);
    }
  },

  createModal: function() {
    return new CkeditorFieldInModal({model:this.model, modelProp:this.modelProp, canEdit:this.canEdit});
  },

  seeLessContent: function(e) {
    e.stopPropagation();
    e.preventDefault();

    //This is absurd, but in seeMoreContent will not restore the "after:" 
    // element to it's original location so we need to re-render here in case 
    // seeMoreContent was called before

    this.render();

    this.ui.seeLess.addClass('hidden');

    this.ellipsis(this.ui.mainfield, this.ui.seeMore);
  },

  /**
   * set the templace in editing mode
   */
  startEditing: function() {
    var editingArea = this.$('#' + this.fieldId).get(0);
    var that = this;

    var config = _.extend({}, this.CKEDITOR_CONFIG, {
      sharedSpaces: { top: this.topId, bottom: this.bottomId }
    });

    //CKEDITOR.basePath = static_url + '/node_modules/ckeditor/';
    this.ckInstance = CKEDITOR.inline(editingArea, config);

    setTimeout(function() {
      if (Ctx.debugRender) {
        console.log("cKEditorField:startEditing() stealing browser focus");
      }
      editingArea.focus();
    }, 100);

    if (this.autosave) {

      this.ckInstance.on('blur', function() {
        /**
        * Firefox triggers the blur event if we paste (ctrl+v)
        * in the ckeditor, so instead of calling the function directly
        * we wait to see if the focus is still in the ckeditor
        */
        setTimeout(function() {

          if (!that.ckInstance || !that.ckInstance.element) return;

          var hasFocus = $(that.ckInstance.element).is(":focus");

          if (!hasFocus) that.saveEdition();

        }, 100);

      });
    }
  },

  /**
   * Destroy the ckeditor instance
   */
  destroy: function() {
    this.ckInstance = null;
  },

  changeToEditMode: function() {
    if (this.canEdit) {
      this.editing = true;
      this.render();
    }
  },

  saveEdition: function(ev) {
    if (ev) {
      ev.stopPropagation();
    }

    var text = this.ckInstance.getData();
    text = $.trim(text);
    if (text != $.trim(this.placeholder) || Ctx.stripHtml(text) == '') {
      /* We never save placeholder values to the model */
      if (this.getTextValue() != text) {
        /* Nor save to the database and fire change events
         * if the value didn't change from the model
         */
        this.setTextValue(text);
        this.trigger('save', [this]);
      }
    }

    this.editing = false;
    this.render();
  },

  cancelEdition: function(ev) {
    if (ev) {
      ev.stopPropagation();
    }

    if (this.ckInstance) {
      var text = this.getTextValue();
      this.ckInstance.setData(text);
    }

    this.editing = false;
    this.render();

    this.trigger('cancel', [this]);
  }

});

var CkeditorFieldInModal = Backbone.Modal.extend({
  constructor: function CkeditorFieldInModal(){
    Backbone.Modal.apply(this, arguments);
  },
  keyControl:false,
  template: '#tmpl-modalWithoutIframe',
  className: 'modal-ckeditorfield popin-wrapper',
  cancelEl: '.close',
  ui: {
    'body': '.js_modal-body'
  },
  initialize:function(options){
    this.model = options.model;
    this.modelProp = options.modelProp;
    this.canEdit = options.canEdit;
    this.autosave = options.autosave;
  },
  serializeData: function(){
    var title = this.model.get('shortTitle');
    return {
      // this assumes the model is an idea, which should now be another case.
      // Probably used for other objects like announcements.
      // REVISIT. Probably use a substring of getTextValue.
      modal_title: title ? title.originalValue() : '',
    };
  },
  onRender: function(){
    var ckeditorField = new cKEditorField({
      'model': this.model,
      'modelProp': this.modelProp,
      'canEdit': this.canEdit,
      'autosave': this.autosave,
      'hideSeeMoreButton':true
    });
    this.$(this.ui.body).html(ckeditorField.render().el);
  }
});

cKEditorField.modalClass = CkeditorFieldInModal;

export default cKEditorField;
