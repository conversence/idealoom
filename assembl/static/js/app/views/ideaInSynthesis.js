/**
 *
 * @module app.views.ideaInSynthesis
 */

import Marionette from "backbone.marionette";

import _ from "underscore";
import IdeaLoom from "../app.js";
import Ctx from "../common/context.js";
import i18n from "../utils/i18n.js";
import Permissions from "../utils/permissions.js";
import CKEditorLSField from "./reusableDataFields/ckeditorLSField.js";
import MessageSendView from "./messageSend.js";
import MessagesInProgress from "../objects/messagesInProgress.js";
import CollectionManager from "../common/collectionManager.js";
import panelSpec from "../models/panelSpec";
import PanelSpecTypes from "../utils/panelSpecTypes";
import viewsFactory from "../objects/viewsFactory";
import groupSpec from "../models/groupSpec";
import Promise from "bluebird";
import LoaderView from "./loaderView.js";
import Analytics from "../internal_modules/analytics/dispatcher.js";
import openIdeaInModal from "./modals/ideaInModal.js";

class IdeaInSynthesisView extends LoaderView.extend({
    synthesis: null,

    /**
     * The template
     * @type {template}
     */
    template: "#tmpl-ideaInSynthesis",

    /**
     * The events
     * @type {Object}
     */
    events: {
        "click .js_synthesis-expression": "onTitleClick",
        "click .js_synthesisIdea": "navigateToIdea",
        "click .js_viewIdeaInModal": "showIdeaInModal",
        "click .synthesisIdea-replybox-openbtn": "focusReplyBox",
        "click .messageSend-cancelbtn": "closeReplyBox",
    },

    modelEvents: {
        //THIS WILL NOT ACTUALLY RUN UNTILL CODE IS REFACTORED SO MODEL IS THE REAL IDEA OR THE TOOMBSTONE.  See initialize - benoitg
        /*'change:shortTitle change:longTitle change:segments':'render'*/
    },

    regions: {
        regionExpression: ".js_region-synthesis-expression",
    },
}) {
    /**
     * @init
     */
    initialize(options) {
        this.synthesis = options.synthesis || null;
        this.messageListView = options.messageListView;
        this.editing = false;
        this.authors = [];
        this.original_idea = undefined;
        this.setLoading(true);

        this.parentPanel = options.parentPanel;
        if (this.parentPanel === undefined) {
            throw new Error("parentPanel is mandatory");
        }

        var that = this;
        var collectionManager = new CollectionManager();
        // Calculate the contributors of the idea: authors of important segments (nuggets)
        // Should match Idea.get_synthesis_contributors in the backend
        function render_with_info(
            allMessageStructureCollection,
            allUsersCollection,
            ideaExtracts
        ) {
            if (!that.isDestroyed()) {
                ideaExtracts
                    .filter(function (segment) {
                        return segment.get("important");
                    })
                    .forEach(function (segment) {
                        var post = allMessageStructureCollection.get(
                            segment.get("idPost")
                        );
                        if (post) {
                            var creator = allUsersCollection.get(
                                post.get("idCreator")
                            );
                            if (creator) {
                                that.authors.push(creator);
                            }
                        }
                    });

                that.setLoading(false);
                that.render();
            }
        }
        // idea is either a tombstone or from a different collection; get the original
        Promise.join(
            collectionManager.getAllIdeasCollectionPromise(),
            collectionManager.getUserLanguagePreferencesPromise(Ctx),
            function (allIdeasCollection, translationData) {
                if (!that.isDestroyed()) {
                    var idea = that.model;
                    var original_idea = undefined;
                    that.translationData = translationData;
                    if (that.synthesis.get("is_next_synthesis")) {
                        original_idea = allIdeasCollection.get(that.model.id);
                    } else {
                        original_idea = allIdeasCollection.get(
                            that.model.get("original_uri")
                        );
                    }
                    if (original_idea) {
                        // original may be null if idea deleted.
                        that.original_idea = original_idea;
                        idea = original_idea;
                    }
                    Promise.join(
                        collectionManager.getAllMessageStructureCollectionPromise(),
                        collectionManager.getAllUsersCollectionPromise(),
                        idea.getExtractsPromise(),
                        render_with_info
                    );

                    //console.log("About to connect idea change event to idea:", idea, "for synthesis: ", that.synthesis);
                    that.listenTo(
                        idea,
                        "change:shortTitle change:longTitle change:segments",
                        function () {
                            /*if (Ctx.debugRender) {
          console.log("idesInSynthesis:change event on original_idea, firing render");
        }*/
                            //
                            console.log("Re-assigning model:", that.model);
                            //This is evil and a stop-gap measure. - benoitg
                            that.model = idea;
                            that.render();
                        }
                    );
                }
            }
        );

        this.listenTo(
            this.parentPanel.getGroupState(),
            "change:currentIdea",
            function (state, currentIdea) {
                that.onIsSelectedChange(currentIdea);
            }
        );
    }

    canEdit() {
        return (
            this.model.userCan(Permissions.EDIT_IDEA) &&
            this.synthesis.get("published_in_post") === null
        );
    }

    serializeData() {
        //As all ideas in a previously posted synthesis are tombstoned, the original idea is
        //gathered from the original_uri attribute and view is re-rendered. Therefore, the
        //original idea is expected to be the one that contants the num_posts field.
        var numMessages;

        var longTitle = this.model.get("longTitle");
        if (this.original_idea) {
            numMessages = this.original_idea.get("num_posts");
        }
        if (!numMessages) {
            numMessages = 0;
        }

        return {
            id: this.model.getId(),
            editing: this.editing,
            longTitle: this.model.getLongTitleDisplayText(this.translationData),
            authors: _.uniq(this.authors),
            subject: longTitle ? longTitle.bestValue(this.translationData) : "",
            canEdit: this.canEdit(),
            isPrimaryNavigationPanel: this.getPanel().isPrimaryNavigationPanel(),
            ctxNumMessages: i18n.sprintf(
                i18n.ngettext(
                    "%d message is available under this idea",
                    "%d messages are available under this idea",
                    numMessages
                ),
                numMessages
            ),
            numMessages: numMessages,
        };
    }

    /**
     * The render
     * @returns {IdeaInSynthesisView}
     */
    onRender() {
        /*if (Ctx.debugRender) {
      console.log("idesInSynthesis:onRender() is firing");
    }*/
        if (!this.isLoading()) {
            Ctx.removeCurrentlyDisplayedTooltips(this.$el);

            if (this.canEdit()) {
                this.$el.addClass("canEdit");
            }

            this.$el.attr("id", "synthesis-idea-" + this.model.id);

            this.onIsSelectedChange(
                this.parentPanel.getGroupState().get("currentIdea")
            );
            Ctx.initTooltips(this.$el);
            this.renderCKEditorIdea();

            //Currently disabled, but will be revived at some point
            //this.renderReplyView();
        }
    }

    /**
     * renders the ckEditor if there is one editable field
     */
    renderCKEditorIdea() {
        var model = this.model.getLongTitleDisplayText(this.translationData);

        var ideaSynthesis = new CKEditorLSField({
            model: this.model,
            translationData: this.translationData,
            modelProp: "longTitle",
            placeholder: model,
            showPlaceholderOnEditIfEmpty: true,
            canEdit: this.canEdit(),
            autosave: true,
            hideButton: true,
        });

        this.showChildView("regionExpression", ideaSynthesis);
    }

    /**
     * renders the reply interface
     */
    renderReplyView() {
        var that = this;
        var partialCtx = "synthesis-idea-" + this.model.getId();
        var partialMessage = MessagesInProgress.getMessage(partialCtx);

        var send_callback = function () {
            IdeaLoom.message_vent.trigger("messageList:currentQuery");
            // If we're in synthesis view, do not reset view to idea view
            that.getPanel()
                .getContainingGroup()
                .setCurrentIdea(that.original_idea, true);
        };

        var replyView = new MessageSendView({
            allow_setting_subject: false,
            reply_message_id: this.synthesis.get("published_in_post"),
            reply_idea: this.original_idea,
            body_help_message: i18n.gettext("Type your response here..."),
            cancel_button_label: null,
            send_button_label: i18n.gettext("Send your reply"),
            subject_label: null,
            default_subject:
                "Re: " +
                Ctx.stripHtml(
                    this.original_idea.getLongTitleDisplayText(
                        this.translationData
                    )
                ).substring(0, 50),
            mandatory_body_missing_msg: i18n.gettext(
                "You did not type a response yet..."
            ),
            mandatory_subject_missing_msg: null,
            msg_in_progress_body: partialMessage["body"],
            msg_in_progress_ctx: partialCtx,
            send_callback: send_callback,
            messageList: this.messageListView,
        });

        this.$(".synthesisIdea-replybox").html(replyView.render().el);
    }

    /**
     *  Focus on the reply box, and open it if closed
     **/
    focusReplyBox() {
        this.openReplyBox();

        var that = this;
        window.setTimeout(function () {
            if (Ctx.debugRender) {
                console.log(
                    "ideaInSynthesis:focusReplyBox() stealing browser focus"
                );
            }
            that.$(".js_messageSend-body").focus();
        }, 100);
    }

    /**
     *  Opens the reply box the reply button
     */
    openReplyBox() {
        this.$(".synthesisIdea-replybox").removeClass("hidden");
    }

    /**
     *  Closes the reply box
     */
    closeReplyBox() {
        this.$(".synthesisIdea-replybox").addClass("hidden");
    }

    /**
     * @event
     */
    onIsSelectedChange(idea) {
        //console.log("IdeaView:onIsSelectedChange(): new: ", idea, "current: ", this.model, this);
        if (idea === this.model || idea === this.original_idea) {
            this.$el.addClass("is-selected");
        } else {
            this.$el.removeClass("is-selected");
        }
    }

    /**
     * @event
     */
    onTitleClick(ev) {
        ev.stopPropagation();
        if (this.canEdit()) {
            this.makeEditable();
        }

        this.navigateToIdea(ev);
    }

    getPanel() {
        return this.parentPanel;
    }

    showIdeaInModal(ev) {
        this.navigateToIdea(ev, true);
    }

    navigateToIdea(ev, forcePopup) {
        var panel = this.getPanel();
        var analytics = Analytics.getInstance();

        analytics.trackEvent(analytics.events.NAVIGATE_TO_IDEA_IN_SYNTHESIS);
        openIdeaInModal(
            panel,
            this.original_idea,
            forcePopup,
            this.translationData
        );
    }

    makeEditable() {
        if (this.canEdit()) {
            this.editing = true;
            this.render();
        }
    }
}

export default IdeaInSynthesisView;
