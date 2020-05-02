/**
 *
 * @module app.views.messageExportModal
 */
import Backbone from "backbone";

import BackboneModal from "backbone.modal";
import i18n from "../utils/i18n.js";
import $ from "jquery";
import _ from "underscore";
import Source from "../models/sources.js";
import FacebookViews from "./facebookViews.js";

class Modal extends Backbone.Modal.extend({
    template: "#tmpl-loader",
    className: "group-modal popin-wrapper",
    cancelEl: ".js_close",
    keyControl: false,

    events: {
        "change .js_export_supportedList": "generateView",
    },
}) {
    initialize(options) {
        console.log("initializing Modal");
        this.$(".bbm-modal").addClass("popin");
        this.$(".js_export_error_message").empty(); //Clear any error message that may have been put there
        this.messageCreator = null;
        this.exportedMessage = options.exportedMessage;
        this.formType = undefined;
        this.currentView = undefined;

        Ctx.setCurrentModalView(this);

        var that = this;
        this.exportedMessage.getCreatorPromise().then(function (user) {
            that.messageCreator = user;
            that.template = "#tmpl-exportPostModal";
            that.render();
        });
    }

    serializeData() {
        if (this.messageCreator) {
            return {
                creator: this.messageCreator.get("name"),
            };
        }
    }

    loadFbView() {
        var fbView = new FacebookViews.init({
            exportedMessage: this.exportedMessage,
            model: new Source.Model.FacebookSinglePostSource(),
        });

        this.$(".js_source-specific-form").html(fbView.render().el);
        //Because we are not yet using marionette's version of Backbone.modal.
        fbView.onRender();
    }

    generateView(event) {
        //Whilst checking for accessTokens, make the region where
        //facebook will be rendered a loader

        var value = this.$(event.currentTarget).find("option:selected").val();

        this.formType = value;

        console.log("Generating the view", value);

        switch (value) {
            case "facebook":
                this.loadFbView();
                break;

            default:
                this.$(".js_source-specific-form").empty();
                this.$(".js_export_error_message").empty();
                break;
        }
    }
}

export default Modal;
