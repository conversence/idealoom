/**
 *
 * @module app.views.synthesisPanel
 */

import IdeaRenderVisitor from "./visitors/ideaRenderVisitor.js";

import * as Sentry from "@sentry/browser";
import _ from "underscore";
import $ from "jquery";
import { CollectionView } from "backbone.marionette";
import IdeaLoom from "../app.js";
import Ctx from "../common/context.js";
import MessageModel from "../models/message.js";
import ideaLink from "../models/ideaLink.js";
import Synthesis from "../models/synthesis.js";
import Idea from "../models/idea.js";
import Permissions from "../utils/permissions.js";
import IdeaFamilyView from "./ideaFamily.js";
import IdeaInSynthesisView from "./ideaInSynthesis.js";
import PanelSpecTypes from "../utils/panelSpecTypes.js";
import BasePanel from "./basePanel.js";
import i18n from "../utils/i18n.js";
import EditableLSField from "./reusableDataFields/editableLSField.js";
import CKEditorLSField from "./reusableDataFields/ckeditorLSField.js";
import CollectionManager from "../common/collectionManager.js";
import Promise from "bluebird";

class SynthesisPanel extends BasePanel.extend({
    template: "#tmpl-synthesisPanel",
    panelType: PanelSpecTypes.SYNTHESIS_EDITOR,
    className: "synthesisPanel",
    gridSize: BasePanel.prototype.SYNTHESIS_PANEL_GRID_SIZE,

    regions: {
        ideas: ".synthesisPanel-ideas",
        title: ".synthesisPanel-title",
        introduction: ".synthesisPanel-introduction",
        conclusion: ".synthesisPanel-conclusion",
    },

    events: {
        "click .synthesisPanel-publishButton": "publish",
    },

    modelEvents: {
        "reset change": "render",
    },

    /**
     * The model
     * @type {Synthesis}
     */
    model: null,

    /**
     * The ideas collection
     * @type {Ideas.Collection}
     */
    ideas: null,

    /**
     * The synthesis ideas collection (owned by the synthesis)
     * @type {Ideas.Collection}
     */
    synthesisIdeas: null,

    /**
     * The synthesis root ideas collection (local)
     * @type {Ideas.Collection}
     */
    synthesisIdeaRoots: null,

    /**
     * Flag
     * @type {boolean}
     */
    collapsed: false,

    showAsMessage: false,
}) {
    /**
     * @init
     */
    initialize(obj) {
        super.initialize(...arguments);
        var that = this;
        var collectionManager = new CollectionManager();

        if (obj.template) {
            this.template = obj.template;
        }
        this.setLoading(true);

        if ("showAsMessage" in obj) {
            this.showAsMessage = obj.showAsMessage;
        }

        //This is used if the panel is displayed as part of a message
        // that publishes this synthesis
        this.messageListView = obj.messageListView;
        this.synthesisIdeaRoots = new Idea.Collection();

        this.focusSubject = false;
        Promise.join(
            collectionManager.getAllSynthesisCollectionPromise(),
            collectionManager.getAllIdeasCollectionPromise(),
            collectionManager.getAllIdeaLinksCollectionPromise(),
            collectionManager.getUserLanguagePreferencesPromise(Ctx),
            function (
                synthesisCollection,
                allIdeasCollection,
                allIdeaLinksCollection,
                translationData
            ) {
                if (!that.isDestroyed()) {
                    that.ideas = allIdeasCollection;
                    var rootIdea = allIdeasCollection.getRootIdea();
                    var raw_ideas;

                    if (!that.model) {
                        //If unspecified, we find the next_synthesis
                        that.model = _.find(
                            synthesisCollection.models,
                            function (model) {
                                return model.get("is_next_synthesis");
                            }
                        );
                        that.bindEvents(
                            that.model,
                            that.getOption("modelEvents")
                        );
                    }
                    that.synthesisIdeas = that.model.getIdeasCollection();
                    that.synthesisIdeas.collectionManager = collectionManager;
                    that.translationData = translationData;
                    that.focusSubject = true;

                    that.listenTo(
                        allIdeaLinksCollection,
                        "reset change:source change:target change:order remove add destroy",
                        function () {
                            //console.log("RE_RENDER FROM CHANGE ON allIdeaLinksCollection");
                            that.render();
                        }
                    );
                    that.setLoading(false);

                    that.render();
                }
            }
        );

        //IdeaLoom.commands.setHandler('synthesisPanel:render', this.render);

        this.propagateVisibility(true);
    }

    getTitle() {
        return i18n.gettext("Synthesis");
    }

    serializeData() {
        var currentUser = Ctx.getCurrentUser();
        var canSend = currentUser.can(Permissions.SEND_SYNTHESIS);
        var canEdit = currentUser.can(Permissions.EDIT_SYNTHESIS);

        var data = {
            canSend: canSend,
            canEdit: canEdit,
            Ctx: Ctx,
        };

        if (this.model) data = _.extend(this.model.toJSON(), data);

        return data;
    }

    /**
     * The render
     * @returns {SynthesisPanel}
     */
    onRender() {
        if (Ctx.debugRender) {
            console.log("synthesisPanel:onRender() is firing");
        }

        if (this.isDestroyed()) {
            return;
        }
        if (this.isLoading()) {
            return;
        }

        var that = this;
        var view_data = {};
        var order_lookup_table = [];
        var roots = [];
        var collectionManager = new CollectionManager();
        var canEdit = Ctx.getCurrentUser().can(Permissions.EDIT_SYNTHESIS);

        Ctx.removeCurrentlyDisplayedTooltips(this.$el);

        function renderSynthesis(ideasCollection, ideaLinksCollection) {
            // Getting the scroll position
            var body = that.$(".body-synthesis");

            var y = body.get(0) ? body.get(0).scrollTop : 0;
            var synthesis_is_published = that.model.get("published_in_post");
            var rootIdea = that.ideas.getRootIdea();

            function inSynthesis(idea) {
                //console.log("Checking",idea,"returning:", retval, "synthesis is next synthesis:", that.model.get('is_next_synthesis'));
                return (
                    !idea.hidden &&
                    idea != rootIdea &&
                    ideasCollection.contains(idea)
                );
            }

            if (rootIdea) {
                ideasCollection.visitDepthFirst(
                    ideaLinksCollection,
                    new IdeaRenderVisitor(
                        view_data,
                        order_lookup_table,
                        roots,
                        inSynthesis
                    ),
                    rootIdea,
                    true
                );
            }

            that.synthesisIdeaRoots.reset(roots);
            var synthesisIdeaRootsView = new CollectionView({
                collection: that.synthesisIdeaRoots,
                childView: IdeaFamilyView,
                childViewOptions: {
                    view_data: view_data,
                    innerViewClass: IdeaInSynthesisView,
                    innerViewClassInitializeParams: {
                        synthesis: that.model,
                        messageListView: that.messageListView,
                        parentPanel: that,
                    },
                },
            });

            that.detachChildView("ideas");
            that.showChildView("ideas", synthesisIdeaRootsView);
            body.get(0).scrollTop = y;
            if (canEdit && !synthesis_is_published) {
                var titleField = new EditableLSField({
                    model: that.model,
                    modelProp: "subject",
                    translationData: that.translationData,
                    class: "panel-editablearea text-bold",
                    "data-tooltip": i18n.gettext(
                        "A short title for the synthesis"
                    ),
                    placeholder: i18n.gettext("New Synthesis"),
                    canEdit: canEdit,
                    focus: that.focusSubject,
                });
                that.showChildView("title", titleField);

                var introductionField = new CKEditorLSField({
                    model: that.model,
                    modelProp: "introduction",
                    translationData: that.translationData,
                    placeholder: i18n.gettext(
                        "You can add an introduction to your synthesis here..."
                    ),
                    showPlaceholderOnEditIfEmpty: true,
                    canEdit: canEdit,
                    autosave: true,
                    hideButton: true,
                });
                that.showChildView("introduction", introductionField);

                var conclusionField = new CKEditorLSField({
                    model: that.model,
                    modelProp: "conclusion",
                    translationData: that.translationData,
                    placeholder: i18n.gettext(
                        "You can add a conclusion to your synthesis here..."
                    ),
                    showPlaceholderOnEditIfEmpty: true,
                    canEdit: canEdit,
                    autosave: true,
                    hideButton: true,
                });
                that.showChildView("conclusion", conclusionField);
            } else {
                // TODO: Use regions here.
                that.$(".synthesisPanel-title").html(
                    that.model.get("subject").bestValue(that.translationData)
                );
                that.$(".synthesisPanel-introduction").html(
                    that.model
                        .get("introduction")
                        .bestValue(that.translationData)
                );
                that.$(".synthesisPanel-conclusion").html(
                    that.model.get("conclusion").bestValue(that.translationData)
                );
            }

            Ctx.initTooltips(that.$el);

            if (
                that.getContainingGroup().model.get("navigationState") ==
                "synthesis"
            ) {
                that.$(".synthesisPanel-introduction")[0].id =
                    "tour_step_synthesis_intro";
                IdeaLoom.tour_vent.trigger("requestTour", "synthesis_intro");
                if (roots.length > 0) {
                    that.$(".synthesisPanel-ideas")[0].id =
                        "tour_step_synthesis_idea1";
                    IdeaLoom.tour_vent.trigger(
                        "requestTour",
                        "synthesis_idea1"
                    );
                }
            }
        }

        if (this.model.get("is_next_synthesis")) {
            collectionManager
                .getAllIdeaLinksCollectionPromise()
                .then(function (ideaLinks) {
                    renderSynthesis(that.synthesisIdeas, ideaLinks);
                });
        } else {
            var synthesisIdeaLinksCollection = new ideaLink.Collection(
                that.model.get("idea_links"),
                { parse: true }
            );
            synthesisIdeaLinksCollection.collectionManager = collectionManager;
            renderSynthesis(this.synthesisIdeas, synthesisIdeaLinksCollection);
        }

        return this;
    }

    /* This will show/hide the checkboxes next to each idea of the tables of ideas when a synthesis creation panel is present/absent. */
    propagateVisibility(isVisible) {
        if (this.showAsMessage) {
            return;
        }
        var el = IdeaLoom.rootView.getRegion("groupContainer").$el;
        if (el) {
            if (isVisible) {
                el.addClass("hasSynthesisPanel");
            } else {
                var groupContainerView = this.getPanelWrapper().groupContent
                    .groupContainer;
                var groups = groupContainerView.findGroupsWithPanelInstance(
                    this.panelType
                );
                if (!groups || (groups && groups.length < 2)) {
                    //console.log("this is the last group which was containing a Synthesis creation panel, so we can remove the CSS class");
                    el.removeClass("hasSynthesisPanel");
                }
            }
        }
    }

    onBeforeDestroy() {
        this.propagateVisibility(false);
    }

    /**
     * Publish the synthesis
     */
    publish() {
        var ok = confirm(
            i18n.gettext(
                "Are you sure you want to publish the synthesis? You will not be able to delete it afterwards, and participants who subscribed to notifications related to the synthesis will receive a notification by email."
            )
        );
        if (ok) {
            this._publish();
        }
    }

    /**
     * Publishes the synthesis
     */
    _publish() {
        this.blockPanel();

        var publishes_synthesis_id = this.model.id;
        var that = this;

        var synthesisMessage = new MessageModel.Model({
            publishes_synthesis_id: publishes_synthesis_id,
            subject: null,
            body: null,
        });

        synthesisMessage.save(null, {
            success: function (model, resp) {
                alert(
                    i18n.gettext("Synthesis has been successfully published!")
                );

                // The next_synthesis is the same idea as before, so no need to reload.
                that.unblockPanel();
            },
            error: function (model, resp) {
                Sentry.captureMessage("Failed publishing synthesis!");
                alert(i18n.gettext("Failed publishing synthesis!"));
                that.model = new Synthesis.Model({ "@id": "next_synthesis" });
                that.model.fetch();
                that.unblockPanel();
            },
        });
    }
}

export default SynthesisPanel;
