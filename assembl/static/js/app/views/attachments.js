/**
 *
 * @module app.views.attachments
 */

import Marionette from "backbone.marionette";

import _ from "underscore";
import $ from "jquery";
import Ctx from "../common/context.js";
import dropdown from "bootstrap-dropdown";
import i18n from "../utils/i18n.js";
import IdeaLoom from "../app.js";
import Types from "../utils/types.js";
import Attachments from "../models/attachments.js";
import Documents from "../models/documents.js";
import Backbone from "backbone";
import BackboneModal from "backbone.modal";
import DocumentViews from "./documents.js";

var TARGET = {
    IDEA: "IDEA",
    MESSAGE: "MESSAGE",
};

/**
 * Represents the link between an object (ex: Message, Idea) and a remote (url)
 * or eventually local document attached to it.
 */
class AbstractAttachmentView extends Marionette.View.extend({
    ui: {
        documentEmbeed: ".js_regionDocumentEmbeed",
    },

    regions: {
        documentEmbeedRegion: "@ui.documentEmbeed",
    },

    events: {},

    modelEvents: {
        change: "render",
    },
}) {
    initialize(options) {
        var d = this.model.getDocument();
        this.uri = d.get("external_url") ? d.get("external_url") : d.get("uri");
    }

    serializeData() {
        return {
            url: this.uri,
            i18n: i18n,
        };
    }

    renderDocument() {
        var documentModel = this.model.getDocument();

        var hash = {
            model: documentModel,
        };

        var documentView;

        if (documentModel.isFileType()) {
            documentView = new DocumentViews.FileView(hash);
        } else {
            documentView = new DocumentViews.DocumentView(hash);
        }
        this.showChildView("documentEmbeedRegion", documentView);
    }

    onRender() {
        //console.log("AbstractAttachmentView: onRender with this.model:",this.model);
        //console.log(this.model.get('attachmentPurpose'), Attachments.attachmentPurposeTypes.DO_NOT_USE.id);
        if (
            this.model.get("attachmentPurpose") !==
            Attachments.attachmentPurposeTypes.DO_NOT_USE.id
        ) {
            this.renderDocument();
        }
    }
}

class AttachmentView extends AbstractAttachmentView.extend({
    template: "#tmpl-attachment",
    className: "attachment",
}) {}

class AttachmentEditableView extends AbstractAttachmentView.extend({
    template: "#tmpl-attachmentEditable",
    className: "attachmentEditable",

    ui: _.extend({}, AbstractAttachmentView.prototype.ui, {
        attachmentPurposeDropdown: ".js_attachmentPurposeDropdownRegion",
    }),

    regions: _.extend({}, AbstractAttachmentView.prototype.regions, {
        attachmentPurposeDropdownRegion: "@ui.attachmentPurposeDropdown",
    }),

    events: _.extend({}, AbstractAttachmentView.prototype.events, {
        "click .js_attachmentPurposeDropdownListItem":
            "purposeDropdownListClick", //Dynamically rendered, do NOT use @ui
    }),

    extras: {},
}) {
    initialize(options) {
        //A parent view is passed which will be used to dictate the lifecycle of document creation/deletion
        AbstractAttachmentView.prototype.initialize.call(this, options);
        //parentView => the container around AttachmentEditableCollectionView, if passed
        this.parentView = options.parent ? options.parent : null;
        var that = this;
        this.extrasAdded = {};
        _.each(that.extras, function (v, k) {
            that.extrasAdded[k] = false;
        });
    }

    serializeData() {
        return {
            header: i18n.sprintf(
                i18n.gettext("For URL %s in the text above"),
                this.uri
            ),
        };
    }

    renderDocument() {
        var documentModel = this.model.getDocument();
        var documentView;

        if (documentModel.isFileType()) {
            documentView = new DocumentViews.FileEditView({
                model: documentModel,
                showProgress: true,
                parentView: this,
            });
        } else {
            documentView = new DocumentViews.DocumentEditView({
                model: documentModel,
                parentView: this,
            });
        }
        this.showChildView("documentEmbeedRegion", documentView);
    }

    onRender() {
        //console.log("AttachmentEditableView onRender called for model", this.model.id);
        AbstractAttachmentView.prototype.onRender.call(this);
        this.populateExtras();
        this.renderAttachmentPurposeDropdown(this._renderAttachmentPurpose());
    }

    _updateExtrasCompleted() {
        var that = this;
        _.each(that.extras, function (v, k) {
            that.extrasAdded[k] = true;
        });
    }

    populateExtras() {
        /*
      Override to populate extras array with HTML array which will be appended to the end of the
      attachment purpose dropdown
      Ensure to update the cache of extras completed. Otherwise, each render will introduce 1 more of the
      extras
     */
        this._updateExtrasCompleted();
    }

    _renderAttachmentPurpose() {
        var purposesHtml = [];
        var that = this;
        if (this.model.get("@type") !== "IdeaAttachment") {
            _.each(Attachments.attachmentPurposeTypes, function (
                attachmentPurposeDef
            ) {
                purposesHtml.push(
                    '<li><a class="js_attachmentPurposeDropdownListItem" data-id="' +
                        attachmentPurposeDef.id +
                        '" data-toggle="tooltip" title="" data-placement="left" data-original-title="' +
                        attachmentPurposeDef.id +
                        '">' +
                        attachmentPurposeDef.label +
                        "</a></li>"
                );
            });
        }
        if (this.extras) {
            _.each(that.extras, function (v, k) {
                if (!that.extrasAdded[k]) {
                    purposesHtml.push(v);
                }
            });
        }

        return purposesHtml;
    }

    /**
     * Renders the messagelist view style dropdown button
     */
    renderAttachmentPurposeDropdown(purposesList) {
        var that = this;
        var html = "";

        html +=
            '<a href="#" class="dropdown-toggle" data-toggle="dropdown" aria-expanded="false">';
        html += '<span class="dropdown-label">';
        html +=
            Attachments.attachmentPurposeTypes[
                this.model.get("attachmentPurpose")
            ].label;
        html += "</span>";
        html += '<span class="icon-arrowdown"></span></a>';
        html += '<ul class="dropdown-menu">';
        html += purposesList ? purposesList.join("") : "";
        html += "</ul>";
        this.ui.attachmentPurposeDropdown.html(html);
    }

    purposeDropdownListClick(ev) {
        // console.log('purposeDropdownListClick():', ev.currentTarget.dataset.id);
        if (
            Attachments.attachmentPurposeTypes[ev.currentTarget.dataset.id] ===
            undefined
        ) {
            throw new Error(
                "Invalid attachment purpose: ",
                ev.currentTarget.dataset.id
            );
        }
        this.model.set("attachmentPurpose", ev.currentTarget.dataset.id);
    }

    onRemoveAttachment(ev) {
        ev.stopPropagation();
        //The model is not persisted if it is in an EditableView, so this does not call DELETE
        //to the backend
        this.model.destroy();
    }
}

class AttachmentFileEditableView extends AttachmentEditableView.extend({
    className: "fileAttachmentEditable",

    ui: _.extend({}, AttachmentEditableView.prototype.ui, {
        remove: ".js_removeAttachment",
    }),

    events: _.extend({}, AttachmentEditableView.prototype.events, {
        "click .js_removeAttachment": "onRemoveAttachment",
    }),
}) {
    populateExtras() {
        var a =
            "<li><a class='js_removeAttachment' data-toggle='tooltip' title='' data-placement='left' data-id='CANCEL_UPLOAD' data-original-title='CANCEL_UPLOAD'>" +
            i18n.gettext("Remove") +
            "</a></li>";
        this.extras["REMOVE"] = a;
        // this._updateExtrasCompleted();
    }

    serializeData() {
        return {
            header: i18n.gettext("For the uploaded file"),
        };
    }
}

/*
  The view used for attachments in the idea panel when attachment is editable
  ie. when the user has the permission to upload a file.
 */
class AttachmentFileEditableViewIdeaPanel extends AttachmentFileEditableView.extend(
    {
        modelEvents: {
            change: "onChange",
            destroy: "onDestroy",
        },
    }
) {
    initialize(options) {
        //Save the attachment as soons as the document is saved
        var doc = this.model.getDocument();
        this.listenToOnce(doc, "sync", this.onDocumentSave);
        AttachmentFileEditableView.prototype.initialize.call(this, options);
    }

    onDocumentSave(documentModel, resp, options) {
        //Save the attachment model as well, as in the idea panel, there is no confirmation
        //to save the attachment
        this.model.save();
    }

    /*
    There is a limit of 1 attachment, so this *should* only be called once
   */
    onChange(e) {
        var domObject = $(".content-ideapanel");
        this.$el.find(".embedded-image-preview").on("load", function () {
            var contentPanelPosition = $(window).height() / 3;
            var imgHeight = $(this).height();
            if (imgHeight > contentPanelPosition) {
                domObject.css("top", contentPanelPosition);
            } else {
                domObject.css("top", imgHeight);
            }
        });
        $('[data-id="DO_NOT_USE"]').hide();
        $('[data-id="EMBED_ATTACHMENT"]').hide();
    }

    onDestroy(e) {
        var domObject = $(".content-ideapanel");
        domObject.css("top", "0px");
    }
}

/*
  Generic view for a file-based attachment that failed to load
 */
class AttachmentEditableErrorView extends AttachmentView {
    initialize(options) {
        AttachmentView.prototype.initialize.call(this, options);
    }

    onRender() {
        var fileName = this.model.getDocument().get("file").name;
        var text = i18n.sprintf(
            i18n.gettext(
                'We are sorry, there was an error during the upload of the file "%s". Please try again.'
            ),
            fileName
        );
        this.$el.html("<div class='error-message'>" + text + "</div>");
    }
}

/*
  The collection view that will display all the attachment types that the message can support in an editable state
 */
class AttachmentEditableCollectionView extends Marionette.CollectionView {
    initialize(options) {
        this.parentView = options.parentView ? options.parentView : null;
        this.limits = options.limits || {};
    }

    /*
    To change the kind of view generated dynamically, subclass and
    override this method to define new behaviour.
   */
    getFileEditView() {
        return AttachmentFileEditableView;
    }

    childView(item) {
        if (item.isFailed()) {
            return AttachmentEditableErrorView;
        }

        var d = item.getDocument();
        switch (d.get("@type")) {
            case Types.DOCUMENT:
                return AttachmentEditableView;
                break;
            case Types.FILE:
                return this.getFileEditView();
                break;
            default:
                return new Error(
                    "Cannot create a CollectionView with a document of @type: " +
                        d.get("@type")
                );
                break;
        }
    }

    childViewOptions() {
        return {
            parent: this,
            limits: this.limits,
        };
    }
}

/*
  An editable view for attachments in the idea panel
 */
class AttachmentEditableCollectionViewIdeaPanel extends AttachmentEditableCollectionView {
    getFileEditView() {
        return AttachmentFileEditableViewIdeaPanel;
    }
}

/*
  A contained view that will show attachments
 */
class AttachmentEditUploadView extends Marionette.View.extend({
    template: "#tmpl-uploadView",

    ui: {
        collectionView: ".js_collection-view",
        errorView: ".js_collection-view-failed",
    },

    regions: {
        collectionRegion: "@ui.collectionView",
        collectionFailedRegion: "@ui.errorView",
    },
}) {
    initialize(options) {
        this.collection = options.collection;
        this.target = options.target || TARGET.MESSAGE;
        this.limits = options.limits;
        //For internal use only. NEVER save this collection to the server!
        if (!this.collection) {
            throw new Error(
                "Cannot instantiate a DocumentEditUploadView without a collection!"
            );
        }

        this.failedCollection = new Attachments.Collection([], {
            objectAttachedToModel: this.collection.objectAttachedToModel,
            failed: true, //Add the flag, so that attachment does not try to validate the collection
        });

        var that = this;
        var createAttachmentEditableCollectionView = function (
            parent,
            collection
        ) {
            if (that.target === TARGET.IDEA) {
                return new AttachmentEditableCollectionViewIdeaPanel({
                    collection: collection,
                    limits: that.limits,
                    parentView: parent,
                });
            }
            return new AttachmentEditableCollectionView({
                collection: collection,
                parentView: parent,
            });
        };

        this.collectionView = createAttachmentEditableCollectionView(
            this,
            this.collection
        );
        this.collectionFailedView = createAttachmentEditableCollectionView(
            this,
            this.failedCollection
        );
    }

    onRender() {
        this.showChildView("collectionRegion", this.collectionView);
        this.showChildView("collectionFailedRegion", this.collectionFailedView);
    }

    failModels(models) {
        _.each(models, function (model) {
            model.setFailed();
        });
        this.collection.remove(models);
        this.failedCollection.add(models);
    }

    failModel(model) {
        return this.failModels([model]);
    }

    getFailedCollection() {
        return this.failedCollection;
    }
}

/*
  Another collection view displaying all attachment types that an IDEA PANEL can support in an EDITABLE state
 */
class AttachmentEditUploadViewModal extends Backbone.Modal.extend({
    template: "#tmpl-modalWithoutIframe",
    className: "modal-token-vote-session popin-wrapper",
    cancelEl: ".close, .js_close",

    ui: {
        body: ".js_modal-body",
    },
}) {
    initialize(options) {
        this.collection = options.collection;
    }

    onRender() {
        var resultView = new AttachmentEditUploadView({
            collection: this.collection,
            target: TARGET.IDEA,
        });
        this.$(this.ui.body).html(resultView.render().el);
    }

    serializeData() {
        return {
            modal_title: i18n.gettext("Upload an Image to the Idea Panel"),
        };
    }
}

/*
  The button view that will be the stand-alone view for the attachment button
 */
class AttachmentUploadButtonView extends Marionette.View.extend({
    template: "#tmpl-attachmentButton",

    ui: {
        button: ".js_upload",
    },

    events: {
        "change @ui.button": "onButtonClick",
    },
}) {
    initialize(options) {
        this.collection = options.collection;
        this.objectAttachedToModel = options.objectAttachedToModel;
        this.limits = options.limits || null;
        this.errorCollection = options.errorCollection || null;
        if (!this.collection || !this.objectAttachedToModel) {
            return new Error(
                "Cannot instantiate an AttachmentUploadButtonView without passing " +
                    "an attachment collection that it would affect!"
            );
        }
    }

    clearErrors() {
        if (this.errorCollection) {
            this.errorCollection.reset();
        }
    }

    onButtonClick(e) {
        //Clear out the errorCollection if passed in
        this.clearErrors();
        this.onFileUpload(e);
    }

    onFileUpload(e) {
        var fs = e.target.files;
        var that = this;

        fs = _.map(fs, function (f) {
            //There will be file duplication because the file is already on the DOM if previously added

            var d = new Documents.FileModel({
                name: f.name,
                mime_type: f.type,
            });
            d.set("file", f);

            var attachment = new Attachments.Model({
                document: d,
                objectAttachedToModel: that.objectAttachedToModel,
                idCreator: Ctx.getCurrentUser().id,
            });

            return attachment;
        });

        this.collection.add(fs);
        //Set to the idea model
    }
}

/*
  An attachment button view that is not based on an icon, but instead is textual
 */
class AttachmentUploadTextView extends AttachmentUploadButtonView.extend({
    template: "#tmpl-attachmentText",
}) {}

/**
 * @class app.views.attachments.AttachmentCollectionView
 */
class AttachmentCollectionView extends Marionette.CollectionView.extend({
    childView: AttachmentView,
}) {}

export default {
    AttachmentEditableView: AttachmentEditableView,
    AttachmentView: AttachmentView,
    AttachmentEditableCollectionView: AttachmentEditableCollectionView,
    AttachmentUploadButtonView: AttachmentUploadButtonView,
    AttachmentUploadTextView: AttachmentUploadTextView,
    AttachmentEditUploadView: AttachmentEditUploadView,
    AttachmentCollectionView: AttachmentCollectionView,
    TARGET: TARGET,
};
