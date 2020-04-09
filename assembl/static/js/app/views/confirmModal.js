/**
 *
 * A generic modal view for alerts. Cases/reasons when we need to use this view instead of a browser confirm:
 * a) When we want users who have checked the "don't show alerts/confirms again" browser checkbox to not have a bad time regretting their click by mistake on a button which does a non-undoable action. For example the "Publish" button in the synthesis creation panel.
 * b) When we want users who have checked the "don't show alerts/confirms again" browser checkbox to not have a bad time not understanding what happens when they click on buttons which explain what will happen next by showing a confirm
 * c) Because lots of people get frightened when they see a browser alert/confirm and think it appears because there has been a bug in the application.
 * d) Because a custom modal popin looks nicer than a browser alert/confirm.
 * @module app.views.confirmModal
 */

import _ from "underscore";

import Backbone from "backbone";
import BackboneModal from "backbone.modal";
import i18n from "../utils/i18n.js";

class ConfirmModal extends Backbone.Modal.extend({
    template: "#tmpl-confirmModal",
    className: "generic-modal popin-wrapper modal-joinDiscussion",
    cancelEl: ".close, .js_close",
    submitEl: ".js_confirm",
}) {
    initialize(options) {
        this.icon = "icon" in options ? options.icon : "icon-discuss";
        this.contentText = "contentText" in options ? options.contentText : "";
        this.onSubmit = "onSubmit" in options ? options.onSubmit : null;
        this.cancelText =
            "cancelText" in options
                ? options.cancelText
                : i18n.gettext("Cancel");
        this.submitText =
            "submitText" in options ? options.submitText : i18n.gettext("OK");
    }

    serializeData() {
        return {
            icon: this.icon,
            contentText: this.contentText,
            cancelText: this.cancelText,
            submitText: this.submitText,
        };
    }

    // called by Backbone.Modal when users clicks on submitEl
    submit(ev) {
        if (_.isFunction(this.onSubmit)) {
            this.onSubmit(ev);
        }
    }
}

export default ConfirmModal;
