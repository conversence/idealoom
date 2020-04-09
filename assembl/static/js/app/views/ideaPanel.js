/**
 *
 * @module app.views.ideaPanel
 */

import $ from "jquery";
import _ from "underscore";
import highlight from "jquery-highlight";
import BackboneSubset from "Backbone.Subset";
import Promise from "bluebird";
import Marionette from "backbone.marionette";

import IdeaLoom from "../app.js";
import Ctx from "../common/context.js";
import i18n from "../utils/i18n.js";
import EditableLSField from "./reusableDataFields/editableLSField.js";
import CKEditorLSField from "./reusableDataFields/ckeditorLSField.js";
import Permissions from "../utils/permissions.js";
import PanelSpecTypes from "../utils/panelSpecTypes.js";
import MessagesInProgress from "../objects/messagesInProgress.js";
import SegmentList from "./segmentList.js";
import Announcements from "./announcements.js";
import Widget from "../models/widget.js";
import AgentViews from "./agent.js";
import WidgetLinks from "./widgetLinks.js";
import WidgetButtons from "./widgetButtons.js";
import CollectionManager from "../common/collectionManager.js";
import BasePanel from "./basePanel.js";
import AttachmentViews from "./attachments.js";
import ConfirmModal from "./confirmModal.js";
import AttachmentModels from "../models/attachments.js";
import Loader from "./loader.js";

class IdeaPanel extends BasePanel.extend({
    template: "#tmpl-ideaPanel",
    className: "ideaPanel",
    minimizeable: true,
    closeable: false,
    gridSize: BasePanel.prototype.IDEA_PANEL_GRID_SIZE,
    minWidth: 295,
    ideaPanelOpensAutomatically: true,
    tooltip: i18n.gettext(
        "Detailed information about the currently selected idea in the Table of ideas"
    ),
    panelType: PanelSpecTypes.IDEA_PANEL,
    ui: {
        postIt: ".postitlist",
        type_selection: ".js_type_selection",
        definition: ".js_editDefinitionRegion",
        longTitle: ".js_editLongTitleRegion",
        deleteIdea: ".js_ideaPanel-deleteBtn",
        clearIdea: ".js_ideaPanel-clearBtn",
        closeExtract: ".js_closeExtract",
        contributorsSection: ".ideaPanel-section-contributors",
        announcement: ".ideaPanel-announcement-region",
        widgetsSection: ".js_ideaPanel-section-widgets",
        adminSection: ".js_ideaPanel-section-admin",
        attachmentButton: ".js_attachment-button",
        mindmapButton: ".js_mindmap-button",
        attachmentImage: ".js_idea-attachment",
        openTargetInPopOver: ".js_openTargetInPopOver",
        pubStateTransition: ".js_transition",
    },
    regions: {
        segmentList: ".postitlist",
        contributors: ".contributors",
        widgetsInteractionRegion: ".js_ideaPanel-section-access-widgets-region",
        widgetsConfigurationInteraction: ".ideaPanel-section-conf-widgets",
        widgetsCreationInteraction: ".ideaPanel-section-create-widgets",
        widgetsSeeResultsInteraction: ".ideaPanel-section-see-results",
        announcementRegion: "@ui.announcement",
        regionLongTitle: "@ui.longTitle",
        regionDescription: "@ui.definition",
        attachmentButton: "@ui.attachmentButton",
        attachment: "@ui.attachmentImage",
    },

    modelEvents: {
        //Do NOT listen to change here
        //'replacedBy': 'onReplaced',
        change: "requestRender",
    },

    events: {
        "dragstart @ui.postIt": "onDragStart", //Fired on the element that is the origin of the drag, so when the user starts dragging one of the extracts CURRENTLY listed in the idea
        "dragend @ui.postIt": "onDragEnd", //Fired on the element that is the origin of the drag

        dragenter: "onDragEnter", //Fired on drop targets. So when the user is dragging something from anywhere and moving the mouse towards this panel
        dragover: "onDragOver", //Fired on drop targets.  Formerly these events were limited to  @ui.postIt, but that resulted in terrible UX.  Let's make the entire idea panel a drop zone
        dragleave: "onDragLeave", //Fired on drop targets.
        drop: "onDrop", //Fired on drop targets.
        "change @ui.type_selection": "onTypeSelectionChange",
        "click @ui.closeExtract": "onSegmentCloseButtonClick",
        "click @ui.clearIdea": "onClearAllClick",
        "click @ui.deleteIdea": "onDeleteButtonClick",
        "click @ui.openTargetInPopOver": "openTargetInPopOver",
        "click @ui.pubStateTransition": "pubStateTransition",
        "click @ui.mindmapButton": "openMindMap",
    },
}) {
    initialize(options) {
        super.initialize(...arguments);
        this.setLoading(true);
        var that = this;
        var collectionManager = new CollectionManager();
        this.panelWrapper = options.panelWrapper;
        this.lastRenderHadModel = false;

        if (!this.model) {
            this.model = this.getGroupState().get("currentIdea");
        }

        collectionManager.getAllWidgetsPromise();

        var pref = Ctx.getPreferences();
        this.ideaPanelOpensAutomatically =
            "idea_panel_opens_automatically" in pref
                ? pref.idea_panel_opens_automatically
                : true;

        /*
      Flag used in order to dynamically calculate the height of the image. Undefined if no attachment
     */
        this.attachmentLoaded = undefined;

        if (!this.isDestroyed()) {
            //Yes, it IS possible the view is already destroyed in initialize, so we check
            this.listenTo(this.getGroupState(), "change:currentIdea", function (
                state,
                currentIdea
            ) {
                if (!this.isDestroyed()) {
                    that.setIdeaModel(currentIdea);
                }
            });

            this.listenTo(
                this.getContainingGroup(),
                "change:pseudoIdea",
                function (currentIdea) {
                    //console.log("Pseudo-idea listen hack fired on ideaPanel");
                    if (!this.isDestroyed()) {
                        that.setIdeaModel(currentIdea);
                    }
                }
            );

            this.listenTo(
                IdeaLoom.other_vent,
                "DEPRECATEDideaPanel:showSegment",
                function (segment) {
                    if (!this.isDestroyed()) {
                        that.showSegment(segment);
                    }
                }
            );

            this.listenTo(
                this.getAttachmentCollection(),
                "sync destroy",
                function (e) {
                    if (!this.isDestroyed()) {
                        that.renderAttachmentButton();
                    }
                }
            );

            //For attachments on ideas, a loaded cover image is always loaded, however,
            //a dynamic calculation must be made on how much of the image can be shown
            this.listenTo(
                this.panelWrapper.model,
                "change:minimized",
                function (model, value, options) {
                    //Must use a setTimeout as the panel animation is not Promisified
                    //The animation duration is available as a view variable
                    var that = this;

                    var timeToVisibleImage =
                        this.panelWrapper.animationDuration / 2;

                    setTimeout(function () {
                        that.checkContentHeight();
                    }, timeToVisibleImage);
                }
            );
            var model = this.model;
            this.model = null;
            Promise.join(
                collectionManager.getIdeaPublicationFlowPromise(),
                collectionManager.getUserLanguagePreferencesPromise(Ctx)
            ).then(([pubFlow, userLangColl]) => {
                that.translationData = userLangColl;
                that.ideaPubFlow = pubFlow;
                that.setIdeaModel(model);
            });
        }
    }

    _calculateContentHeight(domObject, imageDomObject) {
        var contentPanelPosition = $(window).height() / 3;
        var imgHeight = imageDomObject.height();
        if (imgHeight > contentPanelPosition) {
            domObject.css("top", contentPanelPosition);
        } else {
            domObject.css("top", imgHeight);
        }
    }
    /*
    Manages the spacing at the top of the ideaPanel, depending on the panel having an
    attachment or not.
   */
    checkContentHeight() {
        var domObject = this.$(".content-ideapanel");
        var that = this;
        if (
            this.model !== null &&
            this.model.get("attachments") &&
            this.model.get("attachments").length > 0
        ) {
            if (this.attachmentLoaded) {
                var imageDomObject = this.$el.find(".embedded-image-preview");
                this._calculateContentHeight(domObject, imageDomObject);
            } else {
                this.$el
                    .find(".embedded-image-preview")
                    .on("load", function () {
                        that.attachmentLoaded = true;
                        that._calculateContentHeight(domObject, $(this));
                    });
            }
        } else {
            domObject.css("top", "0px");
        }
    }

    requestRender() {
        var that = this;

        setTimeout(function () {
            if (!that.isDestroyed()) {
                //console.log("Render from ideaList requestRender");
                that.render();
            }
        }, 1);
    }

    getTitle() {
        return i18n.gettext("Idea");
    }

    /**
     * This is not inside the template because babel wouldn't extract it in
     * the pot file
     */
    getSubIdeasLabel(subIdeas) {
        if (subIdeas.length == 0) {
            return i18n.gettext("This idea has no sub-ideas");
        } else {
            return i18n.sprintf(
                i18n.ngettext(
                    "This idea has %d sub-idea",
                    "This idea has %d sub-ideas",
                    subIdeas.length
                ),
                subIdeas.length
            );
        }
    }

    getAttachmentCollection() {
        return this.model ? this.model.get("attachments") : null;
    }

    /**
     * This is not inside the template because babel wouldn't extract it in
     * the pot file
     */
    getExtractsLabel() {
        var len = 0;

        if (!this.model) return "";

        if (this.extractListSubset) {
            len = this.extractListSubset.models.length;
        }

        if (len == 0) {
            if (this.model.userCan(Permissions.ADD_EXTRACT)) {
                return i18n.gettext("No extract was harvested");
            } else {
                return i18n.gettext("No important nugget was harvested");
            }
        } else {
            if (this.model.userCan(Permissions.ADD_EXTRACT)) {
                return i18n.sprintf(
                    i18n.ngettext(
                        "%d extract was harvested",
                        "%d extracts were harvested",
                        len
                    ),
                    len
                );
            } else {
                return i18n.sprintf(
                    i18n.ngettext(
                        "%d important nugget was harvested",
                        "%d important nuggets were harvested",
                        len
                    ),
                    len
                );
            }
        }
    }

    renderTemplateGetExtractsLabel() {
        this.$(".js_extractsSummary").html(this.getExtractsLabel());
    }

    renderAttachmentButton() {
        var collection = this.getAttachmentCollection();
        if (collection.length > 0) {
            this.getRegion("attachmentButton").empty();
        } else {
            // var buttonView = new AttachmentViews.AttachmentUploadButtonView({
            var buttonView = new AttachmentViews.AttachmentUploadTextView({
                collection: collection,
                objectAttachedToModel: this.model,
            });
            this.showChildView("attachmentButton", buttonView);
        }
    }

    renderAttachments() {
        var collection = this.getAttachmentCollection();
        var user = Ctx.getCurrentUser();
        if (user.can(Permissions.EDIT_IDEA)) {
            var attachmentView = new AttachmentViews.AttachmentEditUploadView({
                collection: collection,
                target: AttachmentViews.TARGET.IDEA,
            });

            this.showChildView("attachment", attachmentView);
            this.renderAttachmentButton();
        } else {
            var attachmentView = new AttachmentViews.AttachmentCollectionView({
                collection: collection,
            });
            this.showChildView("attachment", attachmentView);
        }
    }

    serializeData() {
        if (Ctx.debugRender) {
            console.log("ideaPanel::serializeData()");
        }

        var subIdeas = {};
        var that = this;
        var currentUser = Ctx.getCurrentUser();
        var canEdit = false;
        var canDelete = false;
        var canAddExtracts = false;
        var canEditNextSynthesis = currentUser.can(Permissions.EDIT_SYNTHESIS);
        var direct_link_relative_url = null;
        var share_link_url = null;
        var currentTypes = null;
        var currentTypeDescriptions = ["", ""];
        var possibleTypes = [];
        var possibleTypeDescriptions = {};
        var locale = Ctx.getLocale();
        var contributors = undefined;
        var pubStateName = null;
        var transitions = [];
        var imported_from_source_name = null;
        var imported_from_id = null;
        var imported_from_url = null;

        if (this.model) {
            subIdeas = this.model.getChildren();
            canEdit = this.model.userCan(Permissions.EDIT_IDEA) || false;
            canDelete = this.model.userCan(Permissions.EDIT_IDEA);
            canAddExtracts = this.model.userCan(Permissions.ASSOCIATE_EXTRACT); //TODO: This is a bit too coarse
            imported_from_source_name = this.model.get(
                "imported_from_source_name"
            );
            imported_from_id = this.model.get("imported_from_id");
            imported_from_url = this.model.get("imported_from_url");
            if (this.parentLink != undefined) {
                currentTypes = this.model.getCombinedSubtypes(this.parentLink);
                possibleTypes = this.model.getPossibleCombinedSubtypes(
                    this.parentLink
                );
                currentTypeDescriptions = this.model.combinedTypeNamesOf(
                    currentTypes,
                    locale
                );
                _.map(possibleTypes, function (types) {
                    var names = that.model.combinedTypeNamesOf(types, locale);
                    possibleTypeDescriptions[types] =
                        names[0] + " → " + names[1];
                });
            }

            direct_link_relative_url = this.model.getRouterUrl({
                parameters: {
                    source: "share",
                },
                relative: true,
            });
            // TODO: Create a share widget class
            share_link_url = Widget.Model.prototype.getObjectShareUrl([
                {
                    u: Ctx.getAbsoluteURLFromRelativeURL(
                        direct_link_relative_url
                    ),
                },
                { t: this.model.getShortTitleSafe(this.translationData) },
                { s: Ctx.getPreferences().social_sharing },
            ]);
            if (Ctx.hasIdeaPubFlow()) {
                const stateLabel = this.model.get("pub_state_name");
                const states = this.ideaPubFlow.get("states");
                if (stateLabel) {
                    const state = states.findByLabel(stateLabel);
                    if (state) {
                        pubStateName = state.nameOrLabel(this.translationData);
                    } else {
                        console.error("Could not find state " + stateLabel);
                    }
                }
                const transitionColl = this.ideaPubFlow
                    .get("transitions")
                    .filter((transition) => {
                        return transition.get("source_label") == stateLabel;
                    })
                    .map((transition) => {
                        const targetLabel = transition.get("target_label"),
                            target = states.findByLabel(targetLabel),
                            targetName = target
                                ? target.nameOrLabel(this.translationData)
                                : targetLabel;
                        transitions.push({
                            name: transition.nameOrLabel(this.translationData),
                            label: transition.get("label"),
                            target_name: targetName,
                            enabled: this.model.userCan(
                                transition.get("req_permission_name")
                            )
                                ? ""
                                : "disabled=true",
                        });
                    });
            }
        }

        return {
            idea: this.model,
            subIdeas,
            translationData: this.translationData,
            canEdit,
            i18n,
            getExtractsLabel: this.getExtractsLabel,
            getSubIdeasLabel: this.getSubIdeasLabel,
            canDelete,
            canEditNextSynthesis,
            canEditExtracts: currentUser.can(Permissions.EDIT_EXTRACT),
            canAddExtracts,
            Ctx,
            pubStateName,
            transitions,
            direct_link_relative_url,
            currentTypes,
            possibleTypes,
            possibleTypeDescriptions,
            imported_from_source_name,
            imported_from_id,
            imported_from_url,
            linkTypeDescription: currentTypeDescriptions[0],
            nodeTypeDescription: currentTypeDescriptions[1],
            share_link_url,
        };
    }

    onRender() {
        var that = this;
        var collectionManager = new CollectionManager();
        var currentUser = Ctx.getCurrentUser();

        if (Ctx.debugRender) {
            console.log("ideaPanel::onRender()");
        }

        Ctx.removeCurrentlyDisplayedTooltips(this.$el);

        Ctx.initTooltips(this.$el);

        if (this.model && this.model.id && this.extractListSubset) {
            //Only fetch extracts if idea already has an id.
            //console.log(this.extractListSubset);
            // display only important extract for simple user
            if (!this.model.userCan(Permissions.ADD_EXTRACT)) {
                this.extractListSubset.models = _.filter(
                    this.extractListSubset.models,
                    function (model) {
                        return model.get("important");
                    }
                );
            }

            this.checkContentHeight();

            this.getExtractslist();

            this.renderShortTitle();

            this.renderAttachments();

            this.renderAnnouncement();

            this.renderCKEditorDescription();

            if (currentUser.can(Permissions.EDIT_SYNTHESIS)) {
                this.renderCKEditorLongTitle();
            }

            this.renderContributors();

            if (
                this.model.userCan(Permissions.EDIT_IDEA) ||
                currentUser.can(Permissions.EDIT_SYNTHESIS)
            ) {
                this.ui.adminSection.removeClass("hidden");
            }

            collectionManager
                .getWidgetsForContextPromise(
                    Widget.Model.prototype.IDEA_PANEL_ACCESS_CTX,
                    that.model
                )
                .then(function (subset) {
                    that.showChildView(
                        "widgetsInteractionRegion",
                        new WidgetButtons.WidgetButtonListView({
                            collection: subset,
                            translationData: that.translationData,
                        })
                    );
                    if (subset.length > 0) {
                        that.ui.widgetsSection.removeClass("hidden");
                    }
                });
            if (currentUser.can(Permissions.ADMIN_DISCUSSION)) {
                collectionManager
                    .getWidgetsForContextPromise(
                        Widget.Model.prototype.IDEA_PANEL_CONFIGURE_CTX,
                        that.model
                    )
                    .then(function (subset) {
                        that.showChildView(
                            "widgetsConfigurationInteraction",
                            new WidgetLinks.WidgetLinkListView({
                                collection: subset,
                            })
                        );
                    });

                //Check that the type of the widgetModel is localType, can see results, then show it.

                that.showChildView(
                    "widgetsCreationInteraction",
                    new WidgetLinks.WidgetLinkListView({
                        context: Widget.Model.prototype.IDEA_PANEL_CREATE_CTX,
                        collection: Widget.localWidgetClassCollection,
                        idea: that.model,
                    })
                );
            }
            this.lastRenderHadModel = true;
        } else {
            this.lastRenderHadModel = false;
        }
    }

    onAttach() {
        if (!this.isDestroyed()) {
            if (!this.ideaPanelOpensAutomatically) {
                this.panelWrapper.minimizePanel(); // even if there is a this.model
            }
        }
    }

    getExtractslist() {
        var that = this;
        var collectionManager = new CollectionManager();

        if (this.extractListSubset) {
            Promise.join(
                collectionManager.getAllExtractsCollectionPromise(),
                collectionManager.getAllUsersCollectionPromise(),
                collectionManager.getAllMessageStructureCollectionPromise(),
                function (
                    allExtractsCollection,
                    allUsersCollection,
                    allMessagesCollection
                ) {
                    that.extractListView = new SegmentList.SegmentListView({
                        collection: that.extractListSubset,
                        allUsersCollection: allUsersCollection,
                        allMessagesCollection: allMessagesCollection,
                    });

                    that.showChildView("segmentList", that.extractListView);
                    that.renderTemplateGetExtractsLabel();
                }
            );
        } else {
            this.renderTemplateGetExtractsLabel();
        }
    }

    renderContributors() {
        var that = this;
        var collectionManager = new CollectionManager();

        collectionManager
            .getAllUsersCollectionPromise()
            .then(function (allAgents) {
                var contributorsRaw = that.model.get("contributors");
                var contributorsId = [];
                var allAgents = allAgents;
                _.each(contributorsRaw, function (contributorId) {
                    contributorsId.push(contributorId);
                });

                //console.log(contributorsId);
                class ContributorAgentSubset extends Backbone.Subset.extend({
                    name: "ContributorAgentSubset",
                }) {
                    sieve(agent) {
                        //console.log(agent.id, _.indexOf(contributorsId, agent.id), contributorsId);
                        return _.indexOf(contributorsId, agent.id) !== -1;
                    }

                    parent() {
                        return allAgents;
                    }
                }

                var contributors = new ContributorAgentSubset();

                //console.log(contributors);
                class avatarCollectionView extends Marionette.CollectionView.extend(
                    {
                        childView: AgentViews.AgentAvatarView,
                    }
                ) {}

                var avatarsView = new avatarCollectionView({
                    collection: contributors,
                });

                that.showChildView("contributors", avatarsView);
                that.ui.contributorsSection
                    .find(".title-text")
                    .html(
                        i18n.sprintf(
                            i18n.ngettext(
                                "%d contributor",
                                "%d contributors",
                                contributorsId.length
                            ),
                            contributorsId.length
                        )
                    );

                if (contributorsId.length > 0) {
                    that.ui.contributorsSection.removeClass("hidden");
                }
            });
    }

    renderShortTitle() {
        var currentUser = Ctx.getCurrentUser();
        var canEdit =
            (this.model && this.model.userCan(Permissions.EDIT_IDEA)) || false;
        var modelId = this.model.id;
        var partialMessage = MessagesInProgress.getMessage(modelId);

        var shortTitleField = new EditableLSField({
            model: this.model,
            modelProp: "shortTitle",
            translationData: this.translationData,
            class: "panel-editablearea text-bold",
            "data-tooltip": i18n.gettext(
                "Short expression (only a few words) of the idea in the table of ideas."
            ),
            placeholder: i18n.gettext("New idea"),
            canEdit: canEdit,
            focus: this.focusShortTitle,
        });
        shortTitleField.renderTo(this.$(".ideaPanel-shorttitle"));
    }

    /**
     * Add a segment
     * @param  {Segment} segment
     */
    addSegment(segment) {
        delete segment.attributes.highlights;
        this.model.addSegment(segment);
    }

    /**
     * Shows the given segment with an small fx
     * @param {Segment} segment
     */
    showSegment(segment) {
        const selector = Ctx.format(".box[data-segmentid={0}]", segment.cid);
        segment.getLatestAssociatedIdeaPromise().then((idea) => {
            if (!idea) {
                return;
            }

            this.setIdeaModel(idea);
            const box = this.$(selector);

            if (box.length) {
                var panelBody = this.$(".panel-body");
                var panelOffset = panelBody.offset().top;
                var offset = box.offset().top;

                // Scrolling to the element
                var target = offset - panelOffset + panelBody.scrollTop();
                panelBody.animate({ scrollTop: target });
                box.highlight();
            }
        });
    }

    onReplaced(newObject) {
        if (this.model !== null) {
            this.stopListening(this.model, "replacedBy acquiredId");
        }

        this.setIdeaModel(newObject);
    }

    /**
     * Set the given idea as the current one
     * @param  {Idea|null} idea
     */
    setIdeaModel(idea, reason) {
        var that = this;
        if (reason === "created") {
            this.focusShortTitle = true;
        } else {
            this.focusShortTitle = false;
        }

        //console.log("setIdeaModel called with", idea, reason);
        if (idea !== this.model) {
            if (this.model !== null) {
                this.stopListening(this.model);
            }

            this.model = idea;

            //Reset the flag for an attachment image loaded. OnRender will recalculate this
            this.attachmentLoaded = undefined;

            //console.log("this.extractListSubset before setIdea:", this.extractListSubset);
            if (this.extractListSubset) {
                this.stopListening(this.extractListSubset);
                this.extractListSubset = null;
            }

            if (this.extractListView) {
                this.extractListView.unbind();
                this.extractListView = null;
            }

            if (this.model) {
                //this.resetView();
                //console.log("setIdeaModel:  we have a model ")
                if (!this.isDestroyed()) {
                    if (that.ideaPanelOpensAutomatically) {
                        this.panelWrapper.unminimizePanel();
                    }
                    if (this.isAttached() && this.lastRenderHadModel) {
                        this.showChildView("segmentList", new Loader());
                    }
                    if (!this.model.id) {
                        //console.log("setIdeaModel:  we have a model, but no id ")
                        if (this.isRenderedAndNotYetDestroyed()) {
                            this.render();
                        }

                        this.listenTo(this.model, "acquiredId", function (m) {
                            // model has acquired an ID. Reset everything.
                            if (!this.isDestroyed()) {
                                var model = that.model;
                                that.model = null;
                                that.setIdeaModel(model, reason);
                            }
                        });
                        this.listenTo(
                            this.model,
                            "change:extra_permissions",
                            function (model, value, options) {
                                that.render();
                            }
                        );
                    } else {
                        //console.log("setIdeaModel:  we have a model, and an id ")
                        this.fetchModelAndRender();
                    }
                }
            }
        }

        if (idea === null) {
            //console.log("setIdeaModel:  we have NO model ")
            //TODO: More sophisticated behaviour here, depending
            //on if the panel was opened by selection, or by something else.
            //If we don't call render here, the panel will not refresh if we delete an idea.
            if (!this.isDestroyed()) {
                this.setLoading(false);
                if (that.ideaPanelOpensAutomatically) {
                    this.panelWrapper.minimizePanel();
                }
            }
            if (this.isRenderedAndNotYetDestroyed()) {
                this.render();
            }
        }
    }

    fetchModelAndRender() {
        var that = this;
        var collectionManager = new CollectionManager();
        var fetchPromise = this.model.fetch({
            data: $.param({ view: "contributors" }),
        });
        Promise.join(
            collectionManager.getAllExtractsCollectionPromise(),
            collectionManager.getAllIdeaLinksCollectionPromise(),
            fetchPromise,
            function (allExtractsCollection, allLinksCollection, fetchedJQHR) {
                //View could be gone, or model may have changed in the meantime
                if (that.model && !that.isDestroyed()) {
                    that.extractListSubset = new SegmentList.IdeaSegmentListSubset(
                        [],
                        {
                            parent: allExtractsCollection,
                            ideaId: that.model.id,
                        }
                    );
                    that.listenTo(
                        that.extractListSubset,
                        "add remove reset change",
                        that.renderTemplateGetExtractsLabel
                    );

                    // temporary code: single parent link for now.
                    that.parentLink = allLinksCollection.findWhere({
                        target: that.model.id,
                    });
                    //console.log("The region:", that.segmentList);
                    that.setLoading(false);
                    that.render();
                }
            }
        );
    }

    onTypeSelectionChange(ev) {
        var vals = ev.target.selectedOptions[0].value.split(/;/, 2);
        this.model.set("subtype", vals[1]);
        this.parentLink.set("subtype", vals[0]);
        // trick: how to make the save atomic?
        this.model.save();
        this.parentLink.save();
    }

    deleteCurrentIdea() {
        // to be deleted, an idea cannot have any children nor segments
        var that = this;

        var children = this.model.getChildren();

        this.blockPanel();
        this.model.getExtractsPromise().then(function (ideaExtracts) {
            that.unblockPanel();
            if (children.length > 0) {
                that.unblockPanel();
                var confirmModal = new ConfirmModal({
                    contentText: i18n.gettext(
                        "You cannot delete an idea while it has sub-ideas."
                    ),
                    submitText: i18n.gettext("OK"),
                    cancelText: null,
                });
                IdeaLoom.rootView.showChildView("slider", confirmModal);
            }

            // Nor has any segments
            else if (ideaExtracts.length > 0) {
                that.unblockPanel();
                var confirmModal = new ConfirmModal({
                    contentText: i18n.gettext(
                        "You cannot delete an idea associated to extracts."
                    ),
                    submitText: i18n.gettext("OK"),
                    cancelText: null,
                });
                IdeaLoom.rootView.showChildView("slider", confirmModal);
            } else if (that.model.get("num_posts") > 0) {
                that.unblockPanel();
                var confirmModal = new ConfirmModal({
                    contentText: i18n.gettext(
                        "You cannot delete an idea associated to comments."
                    ),
                    submitText: i18n.gettext("OK"),
                    cancelText: null,
                });
                IdeaLoom.rootView.showChildView("slider", confirmModal);
            } else {
                var onSubmit = function () {
                    that.model.destroy({
                        success: function () {
                            that.unblockPanel();
                            // UX question: should we go to the parent idea, if any?
                            that.getContainingGroup().setCurrentIdea(null);
                        },
                        error: function (model, resp) {
                            console.error("ERROR: deleteCurrentIdea", resp);
                        },
                    });
                };
                var confirmModal = new ConfirmModal({
                    contentText: i18n.gettext(
                        "Confirm that you want to delete this idea."
                    ),
                    cancelText: i18n.gettext("No"),
                    submitText: i18n.gettext("Yes"),
                    onSubmit: onSubmit,
                });
                IdeaLoom.rootView.showChildView("slider", confirmModal);
            }
        });
    }

    // when the user starts dragging one of the extracts listed in the idea
    // no need for any ev.preventDefault() here
    onDragStart(ev) {
        //console.log("ideaPanel::onDragStart() ev: ", ev);

        var that = this;

        var collectionManager = new CollectionManager();

        //TODO: Deal with local permissions
        if (Ctx.getCurrentUser().can(Permissions.EDIT_EXTRACT)) {
            collectionManager
                .getAllExtractsCollectionPromise()
                .then(function (allExtractsCollection) {
                    ev.currentTarget.style.opacity = 0.4;

                    ev.originalEvent.dataTransfer.effectAllowed = "all";
                    ev.originalEvent.dataTransfer.dropEffect = "move";

                    var cid = ev.currentTarget.getAttribute("data-segmentid");
                    var segment = allExtractsCollection.getByCid(cid);

                    Ctx.showDragbox(ev, segment.getQuote());
                    Ctx.setDraggedSegment(segment);
                })
                .catch(function (error) {
                    console.log("promise error: ", error);
                });
        }
    }

    // "The dragend event is fired when a drag operation is being ended (by releasing a mouse button or hitting the escape key)." quote https://developer.mozilla.org/en-US/docs/Web/Events/dragend
    onDragEnd(ev) {
        //console.log("ideaPanel::onDragEnd() ev: ", ev);

        this.$el.removeClass("is-dragover");
        if (ev && "currentTarget" in ev) {
            ev.currentTarget.style.opacity = 1;
        }
        Ctx.setDraggedAnnotation(null);
        Ctx.setDraggedSegment(null);
    }

    // The dragenter event is fired when the mouse enters a drop target while dragging something
    // We have to define dragenter and dragover event listeners which both call ev.preventDefault() in order to be sure that subsequent drop event will fire => http://stackoverflow.com/questions/21339924/drop-event-not-firing-in-chrome
    // "Calling the preventDefault method during both a dragenter and dragover event will indicate that a drop is allowed at that location." quote https://developer.mozilla.org/en-US/docs/Web/Guide/HTML/Drag_operations#droptargets
    onDragEnter(ev) {
        //console.log("ideaPanel::onDragEnter() ev: ", ev);
        if (ev) {
            ev.preventDefault();
            ev.stopPropagation();
        }
        if (
            Ctx.getDraggedSegment() !== null ||
            Ctx.getDraggedAnnotation() !== null
        ) {
            this.$el.addClass("is-dragover");
        } else {
            console.log("segment or annotation is null");
        }
    }

    // The dragover event is fired when an element or text selection is being dragged over a valid drop target (every few hundred milliseconds).
    // We have to define dragenter and dragover event listeners which both call ev.preventDefault() in order to be sure that subsequent drop event will fire => http://stackoverflow.com/questions/21339924/drop-event-not-firing-in-chrome
    // "Calling the preventDefault method during both a dragenter and dragover event will indicate that a drop is allowed at that location." quote https://developer.mozilla.org/en-US/docs/Web/Guide/HTML/Drag_operations#droptargets
    onDragOver(ev) {
        //console.log("ideaPanel::onDragOver() ev: ", ev);
        if (Ctx.debugAnnotator) {
            console.log(
                "ideaPanel:onDragOver() fired",
                Ctx.getDraggedSegment(),
                Ctx.getDraggedAnnotation()
            );
        }
        if (ev) {
            ev.preventDefault();
            ev.stopPropagation();
        }

        if (ev.originalEvent) {
            ev = ev.originalEvent;
        }

        // /!\ See comment at the top of the onDrop() method
        if (ev && "dataTransfer" in ev) {
            if (
                "effectAllowed" in ev.dataTransfer &&
                (ev.dataTransfer.effectAllowed == "move" ||
                    ev.dataTransfer.effectAllowed == "link")
            ) {
                ev.dataTransfer.dropEffect = ev.dataTransfer.effectAllowed;
            } else {
                ev.dataTransfer.dropEffect = "link";
                ev.dataTransfer.effectAllowed = "link";
            }
        }

        if (
            Ctx.getDraggedSegment() !== null ||
            Ctx.getDraggedAnnotation() !== null
        ) {
            //Because sometimes spurious dragLeave can be fired
            if (!this.$el.hasClass("is-dragover")) {
                console.log("element doesn't have is-dragover class");
                this.$el.addClass("is-dragover");
            }
        }
    }

    // "Finally, the dragleave event will fire at an element when the drag leaves the element. This is the time when you should remove any insertion markers or highlighting. You do not need to cancel this event. [...] The dragleave event will always fire, even if the drag is cancelled, so you can always ensure that any insertion point cleanup can be done during this event." quote https://developer.mozilla.org/en-US/docs/Web/Guide/HTML/Drag_operations
    onDragLeave(ev) {
        //console.log("ideaPanel::onDragLeave() ev: ", ev);
        ev.stopPropagation();
        ev.preventDefault();
        if (ev.currentTarget == ev.target) {
            this.$el.removeClass("is-dragover");
        }
    }

    // /!\ The browser will not fire the drop event if, at the end of the last call of the dragenter or dragover event listener (right before the user releases the mouse button), one of these conditions is met:
    // * one of ev.dataTransfer.dropEffect or ev.dataTransfer.effectAllowed is "none"
    // * ev.dataTransfer.dropEffect is not one of the values allowed in ev.dataTransfer.effectAllowed
    // "If you don't change the effectAllowed property, then any operation is allowed, just like with the 'all' value. So you don't need to adjust this property unless you want to exclude specific types." quote https://developer.mozilla.org/en-US/docs/Web/Guide/HTML/Drag_operations
    // "During a drag operation, a listener for the dragenter or dragover events can check the effectAllowed property to see which operations are permitted. A related property, dropEffect, should be set within one of these events to specify which single operation should be performed. Valid values for the dropEffect are none, copy, move, or link." quote https://developer.mozilla.org/en-US/docs/Web/API/DataTransfer
    // ev.preventDefault() is also needed here in order to prevent default action (open as link for some elements)
    onDrop(ev) {
        //console.log("ideaPanel::onDrop() ev: ", ev);
        if (Ctx.debugAnnotator) {
            console.log("ideaPanel:onDrop() fired");
        }

        if (ev) {
            ev.preventDefault();
        }

        this.$el.removeClass("is-dragover");

        this.$el.trigger("dragleave");

        var segment = Ctx.getDraggedSegment();

        if (segment) {
            this.addSegment(segment);
            Ctx.setDraggedSegment(null);
        }

        var annotation = Ctx.getDraggedAnnotation();

        if (annotation) {
            // Add as a segment
            Ctx.currentAnnotationIdIdea = this.model.getId();
            Ctx.currentAnnotationNewIdeaParentIdea = null;
            Ctx.saveCurrentAnnotationAsExtract();
        }

        if (!segment && !annotation) {
            console.error(
                "Neither a segment nor an annotation was available after Drop"
            );
        }
        this.extractListView.render();
        return;
    }

    onSegmentCloseButtonClick(ev) {
        const cid = ev.currentTarget.getAttribute("data-segmentid");
        const segment = this.extractListSubset.parent.get(cid);
        const ideaId = this.model.getId();
        const link = segment.linkedToIdea(ideaId);
        if (link) link.destroy();
    }

    onClearAllClick(ev) {
        const ok = confirm(
            i18n.gettext(
                "Confirm that you want to send all extracts back to the clipboard."
            )
        );
        const ideaId = this.model.getId();
        if (ok) {
            // Clone first, because the operation removes extracts from the subset.
            const models = _.clone(this.extractListSubset.models);
            _.each(models, function (extract) {
                const link = extract.linkedToIdea(ideaId);
                link.destroy();
            });
        }
    }

    onDeleteButtonClick() {
        this.deleteCurrentIdea();
    }

    renderAnnouncement() {
        var that = this;
        var collectionManager = new CollectionManager();

        if (Ctx.getCurrentUser().can(Permissions.EDIT_IDEA)) {
            this.ui.announcement.removeClass("hidden");
            collectionManager
                .getAllAnnouncementCollectionPromise()
                .then(function (allAnnouncementCollection) {
                    // Filters on only this idea's announce (should be only one...)
                    class AnnouncementIdeaSubset extends Backbone.Subset {
                        beforeInitialize(models, options) {
                            this.idea = options.idea;
                            if (!this.idea) {
                                throw new Error(
                                    "AnnouncementIdeaSubset mush have an idea"
                                );
                            }
                        }

                        sieve(announcement) {
                            return (
                                announcement.get("idObjectAttachedTo") ==
                                this.idea.id
                            );
                        }
                    }

                    var announcementIdeaSubsetCollection = new AnnouncementIdeaSubset(
                        [],
                        {
                            idea: that.model,
                            parent: allAnnouncementCollection,
                        }
                    );
                    var editableAnnouncementView = new Announcements.AnnouncementEditableCollectionView(
                        {
                            collection: announcementIdeaSubsetCollection,
                            objectAttachedTo: that.model,
                        }
                    );
                    that.showChildView(
                        "announcementRegion",
                        editableAnnouncementView
                    );
                });
        }
    }

    renderCKEditorDescription() {
        var that = this;

        var model = this.model.getDefinitionDisplayText(this.translationData);

        if (!model.length) return;

        var description = new CKEditorLSField({
            model: this.model,
            modelProp: "definition",
            translationData: this.translationData,
            placeholder: i18n.gettext(
                "You may want to describe this idea for users here..."
            ),
            showPlaceholderOnEditIfEmpty: false,
            canEdit: Ctx.getCurrentUser().can(Permissions.EDIT_IDEA),
            autosave: true,
            openInModal: true,
        });

        this.showChildView("regionDescription", description);
    }

    renderCKEditorLongTitle() {
        var that = this;

        var model = this.model.getLongTitleDisplayText(this.translationData);
        if (!model.length) return;

        var ckeditor = new CKEditorLSField({
            model: this.model,
            modelProp: "longTitle",
            translationData: this.translationData,
            canEdit: Ctx.getCurrentUser().can(Permissions.EDIT_SYNTHESIS),
            autosave: true,
            openInModal: true,
        });

        this.showChildView("regionLongTitle", ckeditor);
    }

    openTargetInPopOver(evt) {
        console.log("ideaPanel openTargetInPopOver(evt: ", evt);
        return Ctx.openTargetInPopOver(evt);
    }

    openMindMap(evt) {
        const id = this.model.getNumericId();
        const url = Ctx.getApiV2DiscussionUrl(
            "/ideas/" + id + "/mindmap?mimetype=image/svg%2bxml"
        );
        window.open(url, "_il_mindmap");
    }

    pubStateTransition(evt) {
        const transition = evt.target.attributes.data.value;
        const url = this.model.getApiV2Url() + "/do_transition";
        const that = this;
        $.ajax({
            type: "POST",
            contentType: "application/json; charset=UTF-8",
            url,
            data: JSON.stringify({ transition }),
            success: function (data) {
                const state = data.pub_state_name;
                that.model.set("pub_state_name", state);
                that.render();
            },
            error: function (jqXHR, textStatus, errorThrown) {
                console.log(
                    "error! textStatus: ",
                    textStatus,
                    "; errorThrown: ",
                    errorThrown
                );
                // TODO: show error in the UI
            },
        });
    }
}

export default IdeaPanel;
