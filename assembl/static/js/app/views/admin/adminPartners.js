/**
 *
 * @module app.views.admin.adminPartners
 */

import { View, CollectionView } from "backbone.marionette";

import Backbone from "backbone";
import BackboneModal from "backbone.modal";
import IdeaLoom from "../../app.js";
import $ from "jquery";
import CollectionManager from "../../common/collectionManager.js";
import Ctx from "../../common/context.js";
import i18n from "../../utils/i18n.js";
import partnerModel from "../../models/partners.js";
import AdminNavigationMenu from "./adminNavigationMenu.js";

class Partners extends View.extend({
    template: "#tmpl-partnersInAdmin",
    className: "gr",

    ui: {
        partnerItem: ".js_deletePartner",
        partnerItemEdit: ".js_editPartner",
    },

    events: {
        "click @ui.partnerItem": "deletePartner",
        "click @ui.partnerItemEdit": "editPartner",
    },

    modelEvents: {
        change: "render",
    },
}) {
    deletePartner() {
        var that = this;
        this.model.destroy({
            success: function () {
                that.$el.fadeOut();
            },
            error: function () {},
        });
    }

    editPartner() {
        var self = this;

        class Modal extends Backbone.Modal.extend({
            template: _.template($("#tmpl-adminPartnerEditForm").html()),
            className: "partner-modal popin-wrapper",
            cancelEl: ".close, .js_close",
            keyControl: false,
            model: self.model,

            events: {
                "submit #partner-form-edit": "validatePartner",
            },
        }) {
            initialize() {
                this.$(".bbm-modal").addClass("popin");
            }

            validatePartner(e) {
                if (e.target.checkValidity()) {
                    var that = this;

                    self.model.set({
                        description: this.$(".partner-description").val(),
                        homepage: this.$(".partner-homepage").val(),
                        logo: this.$(".partner-logo").val(),
                        name: this.$(".partner-name").val(),
                        is_initiator: this.$(".partner-initiator:checked").val()
                            ? true
                            : false,
                    });

                    self.model.save(null, {
                        success: function (model, resp) {
                            that.triggerSubmit(e);
                        },
                        error: function (model, resp) {
                            console.log(resp);
                        },
                    });
                }

                return false;
            }
        }

        var modal = new Modal();

        IdeaLoom.rootView.showChildView("slider", modal);
    }
}

class PartnerList extends CollectionView.extend({
    childView: Partners,

    collectionEvents: {
        "add sync": "render",
    },
}) {}

class adminPartners extends View.extend({
    template: "#tmpl-adminPartners",
    className: "admin-notifications",

    ui: {
        partners: ".js_addPartner",
        close: ".bx-alert-success .bx-close",
    },

    regions: {
        partner: "#partner-content",
        navigationMenuHolder: ".navigation-menu-holder",
    },

    events: {
        "click @ui.partners": "addNewPartner",
        "click @ui.close": "close",
    },
}) {
    serializeData() {
        return {
            Ctx: Ctx,
        };
    }

    onRender() {
        var that = this;
        var collectionManager = new CollectionManager();

        Ctx.initTooltips(this.$el);

        collectionManager
            .getAllPartnerOrganizationCollectionPromise()
            .then(function (allPartnerOrganization) {
                var partnerList = new PartnerList({
                    collection: allPartnerOrganization,
                });

                that.partners = allPartnerOrganization;

                that.showChildView("partner", partnerList);
            });

        var menu = new AdminNavigationMenu.discussionAdminNavigationMenu({
            selectedSection: "partners",
        });
        this.showChildView("navigationMenuHolder", menu);
    }

    close() {
        this.$(".bx-alert-success").addClass("hidden");
    }

    addNewPartner() {
        var self = this;

        class Modal extends Backbone.Modal.extend({
            template: _.template($("#tmpl-adminPartnerForm").html()),
            className: "partner-modal popin-wrapper",
            cancelEl: ".close, .js_close",
            keyControl: false,

            events: {
                "submit #partner-form": "validatePartner",
            },
        }) {
            initialize() {
                this.$(".bbm-modal").addClass("popin");
            }

            validatePartner(e) {
                if (e.target.checkValidity()) {
                    var inputs = document.querySelectorAll(
                        "#partner-form *[required]"
                    );
                    var that = this;

                    var partner = new partnerModel.Model({
                        description: this.$(".partner-description").val(),
                        homepage: this.$(".partner-homepage").val(),
                        logo: this.$(".partner-logo").val(),
                        name: this.$(".partner-name").val(),
                        is_initiator: this.$(".partner-initiator:checked").val()
                            ? true
                            : false,
                    });

                    partner.save(null, {
                        success: function (model, resp) {
                            that.destroy();
                            $(inputs).val("");
                            self.partners.fetch();
                        },
                        error: function (model, resp) {
                            console.log(resp);
                        },
                    });
                }

                return false;
            }
        }

        var modal = new Modal();

        IdeaLoom.rootView.showChildView("slider", modal);
    }
}

export default adminPartners;
