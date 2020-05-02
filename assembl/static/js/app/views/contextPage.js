/**
 *
 * @module app.views.contextPage
 */

import { View, CollectionView } from "backbone.marionette";

import IdeaLoom from "../app.js";
import Ctx from "../common/context.js";
import CollectionManager from "../common/collectionManager.js";
import $ from "jquery";
import _ from "underscore";
import i18n from "../utils/i18n.js";
import Moment from "moment";
import BackboneSubset from "Backbone.Subset";
import Permissions from "../utils/permissions.js";
import PanelSpecTypes from "../utils/panelSpecTypes.js";
import BasePanel from "./basePanel.js";
import CKEditorField from "./reusableDataFields/ckeditorField.js";
import Statistics from "./statistics.js";
import Types from "../utils/types.js";
import Promise from "bluebird";

class Partner extends View.extend({
    template: "#tmpl-partnerItem",
    className: "gu gu-2of7 partnersItem mrl",
}) {
    serializeData() {
        return {
            organization: this.model,
        };
    }

    templateContext() {
        return {
            htmlEntities: function (str) {
                return String(str)
                    .replace(/&/g, "&amp;")
                    .replace(/</g, "&lt;")
                    .replace(/>/g, "&gt;")
                    .replace(/"/g, "&quot;");
            },
        };
    }
}

class PartnerListBody extends CollectionView.extend({
    childView: Partner,
}) {}

class PartnerList extends View.extend({
    template: "#tmpl-partnerList",
    className: "gr mvxl",

    regions: {
        partnerListBody: "div.partnersList",
    },
}) {
    initialize(options) {
        this.nbOrganisations = options.nbOrganisations;
    }

    onRender() {
        this.showChildView(
            "partnerListBody",
            new PartnerListBody({
                collection: this.collection,
            })
        );
    }

    serializeData() {
        return {
            userCanEditDiscussion: Ctx.getCurrentUser().can(
                Permissions.ADMIN_DISCUSSION
            ),
            nbOrganisations: this.nbOrganisations,
            urlEdit: "/" + Ctx.getDiscussionSlug() + "/partners",
        };
    }
}

class Synthesis extends View.extend({
    template: "#tmpl-synthesisContext",

    events: {
        "click .js_readSynthesis": "readSynthesis",
    },

    modelEvents: {
        change: "render",
    },
}) {
    initialize(options) {
        var that = this;

        this.model = new Backbone.Model();

        //WRITEME:  Add a listenTo on allSynthesisCollection to get an updated synthesis
        var synthesisMessage = options.allMessageStructureCollection.getLastSynthesisPost();
        if (synthesisMessage) {
            var synthesis = options.allSynthesisCollection.get(
                synthesisMessage.get("publishes_synthesis")
            );
            this.model.set({
                created: synthesisMessage.get("date"),
                introduction: synthesis.get("introduction"),
            });
        } else {
            this.model.set({
                empty: i18n.gettext(
                    "No synthesis of the discussion has been published yet"
                ),
            });
        }
    }

    serializeData() {
        return {
            synthesis: this.model,
            ctx: Ctx,
        };
    }

    readSynthesis() {
        IdeaLoom.other_vent.trigger(
            "DEPRECATEDnavigation:selected",
            "synthesis"
        );
    }
}

class Instigator extends View.extend({
    template: "#tmpl-instigator",

    ui: {
        instigatorDescriptionRegion: ".js_region-instigator-editor",
    },

    regions: {
        regionInstigatorDescription: "@ui.instigatorDescriptionRegion",
    },

    events: {},
}) {
    initialize() {}

    serializeData() {
        return {
            instigator: this.model,
            Ctx: Ctx,
            userCanEditDiscussion: Ctx.getCurrentUser().can(
                Permissions.ADMIN_DISCUSSION
            ),
        };
    }

    onRender() {
        this.renderCKEditorInstigator();
    }

    renderCKEditorInstigator() {
        var uri = this.model.id.split("/")[1];
        this.model.url =
            Ctx.getApiV2DiscussionUrl("partner_organizations/") + uri;

        var instigator = new CKEditorField({
            model: this.model,
            modelProp: "description",
            canEdit: Ctx.getCurrentUser().can(Permissions.ADMIN_DISCUSSION),
        });

        this.showChildView("regionInstigatorDescription", instigator);
    }

    templateContext() {
        return {
            editInstigatorUrl: function () {
                return "/" + Ctx.getDiscussionSlug() + "/partners";
            },
        };
    }
}

class Introduction extends View.extend({
    template: "#tmpl-introductions",

    ui: {
        introduction: ".js_editIntroduction",
        objective: ".js_editObjective",
        seeMoreIntro: ".js_introductionSeeMore",
        seeMoreObjectives: ".js_objectivesSeeMore",
        introductionEditor: ".context-introduction-editor",
        objectiveEditor: ".context-objective-editor",
    },

    regions: {
        objectiveEditorRegion: "@ui.objectiveEditor",
        introductionEditorRegion: "@ui.introductionEditor",
    },

    events: {
        "click @ui.seeMoreIntro": "seeMore",
        "click @ui.seeMoreObjectives": "seeMore",
        "click @ui.introduction": "editIntroduction",
        "click @ui.objective": "editObjective",
    },
}) {
    initialize() {
        this.editingIntroduction = false;
        this.editingObjective = false;
    }

    serializeData() {
        return {
            context: this.model,
            editingIntroduction: this.editingIntroduction,
            editingObjective: this.editingObjective,
            userCanEditDiscussion: Ctx.getCurrentUser().can(
                Permissions.ADMIN_DISCUSSION
            ),
        };
    }

    onRender() {
        this.renderCKEditorIntroduction();
        this.renderCKEditorObjective();
    }

    editIntroduction() {
        if (Ctx.getCurrentUser().can(Permissions.ADMIN_DISCUSSION)) {
            this._introductionEditor.changeToEditMode();
        }
    }

    editObjective() {
        if (Ctx.getCurrentUser().can(Permissions.ADMIN_DISCUSSION)) {
            this._objectiveEditor.changeToEditMode();
        }
    }

    renderCKEditorIntroduction() {
        var that = this;
        var area = this.$(".context-introduction-editor");

        var introduction = new CKEditorField({
            model: this.model,
            modelProp: "introduction",
            canEdit: Ctx.getCurrentUser().can(Permissions.ADMIN_DISCUSSION),
        });

        this.showChildView("introductionEditorRegion", introduction);
        this._introductionEditor = introduction;
    }

    renderCKEditorObjective() {
        var that = this;
        var area = this.$(".context-objective-editor");

        var objective = new CKEditorField({
            model: this.model,
            modelProp: "objectives",
            canEdit: Ctx.getCurrentUser().can(Permissions.ADMIN_DISCUSSION),
        });

        this.showChildView("objectiveEditorRegion", objective);
        this._objectiveEditor = objective;
    }
}

class ContextPage extends View.extend({
    template: "#tmpl-contextPage",
    panelType: PanelSpecTypes.DISCUSSION_CONTEXT,
    className: "contextPanel",
    gridSize: BasePanel.prototype.CONTEXT_PANEL_GRID_SIZE,
    hideHeader: true,

    regions: {
        organizations: "#context-partners",
        synthesis: "#context-synthesis",
        statistics: "#context-statistics",
        instigator: "#context-instigator",
        introductions: "#context-introduction",
    },
}) {
    getTitle() {
        return i18n.gettext("Home"); // unused
    }

    onRender() {
        var that = this;
        var collectionManager = new CollectionManager();

        Promise.join(
            collectionManager.getDiscussionModelPromise(),
            collectionManager.getAllPartnerOrganizationCollectionPromise(),
            collectionManager.getAllMessageStructureCollectionPromise(),
            collectionManager.getAllSynthesisCollectionPromise(),

            function (
                DiscussionModel,
                AllPartner,
                allMessageStructureCollection,
                allSynthesisCollection
            ) {
                try {
                    if (!that.isDestroyed()) {
                        var partnerInstigator = AllPartner.find(function (
                            partner
                        ) {
                            return partner.get("is_initiator");
                        });

                        /*
                From Marionette doc for LayoutView:
                <<
                Once you've rendered the layoutView, you now have direct access
                to all of the specified regions as region managers.

                layoutView.showChildView('menu', new MenuView());
                >>
                This means layoutView.getRegion('...').show(...) has to be called after the layoutview has been rendered.
                So it has to be called in an onRender() method.
                But when the page http://localhost:6543/sandbox/posts/local%3AContent%2F568 is accessed using Chromium, we get this error:
                TypeError: Cannot read property 'show' of undefined
                So, getRegion() does not seem to always find the region, why?
                This current onBeforeRender() method seems to be called twice, so maybe the view is destroyed or replaced before getting the result of the promise.
                This answer http://stackoverflow.com/questions/25070398/re-rendering-of-backbone-marionette-template-on-trigger-event suggests that we should use listeners instead.
                We may have to dig in this direction. Until then, and because the view is rendered correctly the second time, we simply ignore the problem, using a try/catch.
                */

                        var introduction = new Introduction({
                            model: DiscussionModel,
                        });
                        that.showChildView("introductions", introduction);

                        if (partnerInstigator !== undefined) {
                            var instigator = new Instigator({
                                model: partnerInstigator,
                            });
                            that.showChildView("instigator", instigator);
                        }

                        that.showChildView("statistics", new Statistics());

                        var synthesis = new Synthesis({
                            allMessageStructureCollection: allMessageStructureCollection,
                            allSynthesisCollection: allSynthesisCollection,
                        });
                        that.showChildView("synthesis", synthesis);

                        class NonInstigatorSubset extends Backbone.Subset {
                            sieve(partner) {
                                return partner !== partnerInstigator;
                            }
                        }

                        var nonInstigatorSubset = new NonInstigatorSubset([], {
                            parent: AllPartner,
                        });

                        var partners = new PartnerList({
                            nbOrganisations: nonInstigatorSubset.length,
                            collection: nonInstigatorSubset,
                        });
                        that.showChildView("organizations", partners);
                    }
                } catch (e) {
                    console.log(
                        "Aborting rendering of ContextPanel's regions, probably because the view was replaced since."
                    );

                    console.log("Here is the error:");
                    console.log(e);
                }
            }
        );
    }
}

export default ContextPage;
