/**
 *
 * @module app.views.ideaInIdeaList
 */

import Backbone from "backbone";

import _ from "underscore";
import $ from "jquery";
import Types from "../utils/types.js";
import classlist from "classlist-polyfill";
import IdeaLoom from "../app.js";
import Ctx from "../common/context.js";
import Permissions from "../utils/permissions.js";
import UserCustomData from "../models/userCustomData.js";
import PanelSpecTypes from "../utils/panelSpecTypes.js";
import scrollUtils from "../utils/scrollUtils.js";
import Marionette from "backbone.marionette";
import Analytics from "../internal_modules/analytics/dispatcher.js";

class IdeaInIdeaListView extends Marionette.View.extend({
    /**
     * Tag name
     * @type {string}
     */
    tagName: "div",

    /**
     * The template
     * @type {template}
     */
    template: "#tmpl-ideaInIdeaList",

    /**
     * Counter used to open the idea when it is dragover
     * @type {number}
     */
    dragOverCounter: 0,

    /**
     * Shortcut to this.parentPanel.getTableOfIdeasCollapsedState()
     * Stores (in UserCustomData per-discussion key/value store) the collapsed state of each idea. Model is in the following form: {42: true, 623: false} where each key is the numeric id of an idea
     * @type {UserCustomData.Model}
     */
    tableOfIdeasCollapsedState: null,

    /**
     * Shortcut to this.parentPanel.getDefaultTableOfIdeasCollapsedState()
     * Stores (in DiscussionPreference per-discussion key/value store) the collapsed state of each idea. Model is in the following form: {42: true, 623: false} where each key is the numeric id of an idea
     * @type {DiscussionPreference.Model}
     */
    defaultTableOfIdeasCollapsedState: null,

    regions: {
        regionChildren: ".idealist-children",
    },

    /**
     * The events
     * @type {Object}
     */
    events: {
        'change input[type="checkbox"]': "onCheckboxChange",
        "click .idealist-title": "onTitleClick",
        "click .idealist-abovedropzone": "onTitleClick",
        "click .idealist-dropzone": "onTitleClick",
        "click .js_idealist-title-unread-count": "onUnreadCountClick",
        "click .idealist-arrow": "toggle",
        "dragstart .idealist-body": "onDragStart", // when the user starts dragging this idea
        "dragend .idealist-body": "onDragEnd",
        "dragenter .idealist-body": "onDragEnter",
        "dragover .idealist-body": "onDragOver",
        "dragleave .idealist-body": "onDragLeave",
        "drop .idealist-body": "onDrop",
        "mouseleave > .idealist-body > .idealist-title": "onMouseLeave",
        "mouseenter > .idealist-body > .idealist-title": "onMouseEnter",
    },
}) {
    /**
     * @init
     * @param {dict} options:
     *   visitorData: data from the render visitor
     *   are the last child of their respective parents.
     */
    initialize(options) {
        var that = this;
        this.visitorData = options.visitorData;
        this.parentPanel = options.parentPanel;
        this.translationData = options.translationData;
        if (this.parentPanel === undefined) {
            throw new Error("parentPanel is mandatory");
        }

        if (options.groupContent) {
            this._groupContent = options.groupContent;
        } else {
            throw new Error(
                "groupContent must be passed in constructor options"
            );
        }
        this.listenTo(this.model, "change", this.render);
        this.listenTo(this.model, "replacedBy", this.onReplaced);

        this.listenTo(
            this.parentPanel.getGroupState(),
            "change:currentIdea",
            function (state, currentIdea) {
                if (!that.isDestroyed()) {
                    that.onIsSelectedChange(currentIdea);
                }
            }
        );

        // TODO: Detect a change in current synthesis
        Ctx.getCurrentSynthesisDraftPromise().then(function (synthesis) {
            if (!that.isDestroyed()) {
                that.synthesis = synthesis;
                that.render();
                that.listenTo(
                    synthesis.getIdeasCollection(),
                    "add remove reset",
                    function () {
                        if (!that.isDestroyed()) {
                            that.render();
                        }
                    }
                );
            }
        });

        this.tableOfIdeasCollapsedState = that.parentPanel
            ? that.parentPanel.getTableOfIdeasCollapsedState()
            : null;
        this.defaultTableOfIdeasCollapsedState = that.parentPanel
            ? that.parentPanel.getDefaultTableOfIdeasCollapsedState()
            : null;
        if (
            this.tableOfIdeasCollapsedState &&
            this.defaultTableOfIdeasCollapsedState &&
            that.model
        ) {
            var id = that.model.getNumericId();
            if (id) {
                this.listenTo(
                    this.tableOfIdeasCollapsedState,
                    "change:" + id,
                    that.onIdeaCollaspedStateChange
                );
                this.listenTo(
                    this.defaultTableOfIdeasCollapsedState,
                    "change:" + id,
                    that.onIdeaCollaspedStateChange
                );
                // FIXME: for now, event does not seem to be triggered when I make changes, so I have to call explicitly a render() of the table of ideas
            }
        }
    }

    serializeData() {
        var data = this.model.toJSON();
        var model_type = this.model.get("@type");
        _.extend(data, render_data);
        data.shortTitle = this.model.getShortTitleDisplayText(
            this.translationData
        );
        if (data.longTitle) {
            data.longTitle =
                " - " +
                data.longTitle.bestValue(this.translationData).substr(0, 50);
        }
        // TODO: take a short-ish preview?
        data.textDefinition = data.definition
            ? Ctx.escapeHtml(
                  Ctx.stripHtml(
                      this.model.getDefinitionDisplayText(this.translationData)
                  )
              )
            : null;

        data.Ctx = Ctx;
        data.idea_css_class = this.model.getCssClassFromId();
        if (
            Types.isInstance(model_type, Types.IDEA) &&
            model_type != Types.ROOT_IDEA
        ) {
            var visitorData = this.visitorData;
            var render_data = visitorData[this.model.getId()];
            if (this.synthesis != undefined) {
                data.inNextSynthesis =
                    this.synthesis.getIdeasCollection().get(this.model.id) !==
                    undefined;
            }
            data.linkType = render_data.last_link.get("subtype");
            _.extend(data, render_data);
        }
        return data;
    }

    /**
     * The render
     * @returns {IdeaView}
     */
    onRender() {
        var that = this;
        var visitorData = this.visitorData;
        var idea_render_data = visitorData[this.model.getId()];

        this.$el.addClass("idealist-item");
        Ctx.removeCurrentlyDisplayedTooltips(this.$el);

        this.onIsSelectedChange(
            this.parentPanel.getGroupState().get("currentIdea")
        );

        this.applyCustomCollapsedState();

        var ideaFamilies = new ideaListIdeaFamilyCollectionView({
            collection: new Backbone.Collection(idea_render_data["children"]),
        });
        ideaFamilies.childViewOptions = {
            parentPanel: that.parentPanel,
            groupContent: that._groupContent,
            visitorData: visitorData,
            synthesis: that.synthesis,
            translationData: that.translationData,
        };
        that.showChildView("regionChildren", ideaFamilies);
        if (Ctx.isSmallScreen()) {
            var screenSize = window.innerWidth;
            //TO FIX : impossible to add event marionette on this class: 'idealist-title-unread'
            $(".idealist-title-unread")
                .off("click")
                .on("click", function () {
                    //If it's a small screen detected => scroll to the right
                    scrollUtils.scrollToNextPanel(
                        ".groupsContainer",
                        100,
                        screenSize
                    );
                });
        }
    }

    /**
     * Show the childen
     */
    open() {
        this.$el.addClass("is-open");
    }

    /**
     * Hide the childen
     */
    close() {
        this.$el.removeClass("is-open");
    }

    getIsCollapsedState() {
        return !this.$el.hasClass("is-open");
    }

    saveCollapsedState(isCollapsed) {
        this.parentPanel.saveIdeaCollapsedState(this.model, isCollapsed);
    }

    /**
     * @event
     */
    onIsSelectedChange(idea) {
        //console.log("IdeaView:onIsSelectedChange(): new: ", idea, "current: ", this.model, this);
        if (idea === this.model) {
            this.$el.addClass("is-selected");
        } else {
            this.$el.removeClass("is-selected");
        }
    }

    /**
     * @event
     */
    onMouseEnter(idea) {
        this.$("> .idealist-body").addClass("is-hovered");
    }

    /**
     * @event
     */
    onMouseLeave(idea) {
        this.$("> .idealist-body").removeClass("is-hovered");
    }

    /**
     * @event
     */
    onReplaced(newObject) {
        this.model = newObject;
    }

    getContainingGroup() {
        return this._groupContent;
    }

    /**
     * @event
     */
    onCheckboxChange(ev) {
        var that = this;
        var checked = ev.currentTarget.checked;

        ev.stopPropagation();
        Ctx.getCurrentSynthesisDraftPromise().then(function (synthesis) {
            if (that.model) {
                //once marionettized, replace with: if (!that.isDestroyed()) {
                var ideaCollection = synthesis.getIdeasCollection();
                if (checked) {
                    ideaCollection.add(that.model);
                } else {
                    ideaCollection.remove(that.model);
                }
            }
        });
    }

    /**
     * @param is_unread:  Filter on the unread status of messages
     *                      false: only read messages
     *                      true: only unread messages
     *                      null: don't filter
     */
    doIdeaChange(is_unread) {
        var analytics = Analytics.getInstance();
        //console.log('Tracking event on idea ', this.model.getShortTitleDisplayText(this.translationData))
        if (!is_unread) {
            analytics.trackEvent(analytics.events.OPEN_IDEA_IN_TABLE_OF_IDEAS);
        } else {
            analytics.trackEvent(
                analytics.events.OPEN_IDEA_NEW_MESSAGES_IN_TABLE_OF_IDEAS
            );
        }
        analytics.trackEvent(
            analytics.events.NAVIGATE_TO_IDEA_IN_TABLE_OF_IDEAS
        );
        this._groupContent.setCurrentIdea(this.model);
        var messageListView = this._groupContent.findViewByType(
            PanelSpecTypes.MESSAGE_LIST
        );
        if (messageListView) {
            //Syncing with current idea below isn't sufficient, as we need to set/unset the unread filter
            messageListView.trigger(
                "messageList:addFilterIsRelatedToIdea",
                this.model,
                is_unread
            );
        }
    }

    /**
     * @event
     * Select this idea as the current idea
     */
    _onTitleClick(e, is_unread) {
        e.stopPropagation();
        this.doIdeaChange(is_unread);

        if (Ctx.getCurrentUserId()) {
            // tell the backend that the idea was read
            $.ajax(
                Ctx.getApiV2DiscussionUrl(
                    "ideas/" + this.model.getNumericId() + "/actions"
                ),
                {
                    method: "POST",
                    contentType: "application/json",
                    data: '{"@type":"ViewIdea"}',
                }
            );
        }

        if (this.getIsCollapsedState()) {
            this.open();
            // we have just changed the collapsed state by calling open() or close()
            this.saveCollapsedState(this.getIsCollapsedState());
        }
        if (Ctx.isSmallScreen()) {
            var screenSize = window.innerWidth;
            //If it's a small screen detected => scroll to the right by clicking on an idea
            scrollUtils.scrollToNextPanel(".groupsContainer", 1500, screenSize);
        }
    }

    /**
     * @event
     * Select this idea as the current idea
     */
    onTitleClick(e) {
        this._onTitleClick(e, null);
    }

    /**
     * @event
     * Select this idea as the current idea, and show only unread messages of this idea
     */
    onUnreadCountClick(e) {
        this._onTitleClick(e, true);
    }

    /**
     * @event
     * when the user starts dragging this idea
     */
    onDragStart(ev) {
        //console.log("ideaInIdeaList::onDragStart() ev: ", ev);
        if (ev) {
            ev.stopPropagation();
            IdeaLoom.idea_vent.trigger("idea:dragStart", this.model);
        }

        if (this.model.userCan(Permissions.ASSOCIATE_IDEA)) {
            ev.currentTarget.style.opacity = 0.4;
            ev.originalEvent.dataTransfer.effectAllowed = "move";
            ev.originalEvent.dataTransfer.dropEffect = "move";

            Ctx.showDragbox(
                ev,
                this.model.getShortTitleSafe(this.translationData)
            );
            Ctx.draggedIdea = this.model;
        }
    }

    /**
     * @event
     */
    onDragEnd(ev) {
        //console.log("ideaInIdeaList::onDragEnd() ev: ", ev);
        if (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            IdeaLoom.idea_vent.trigger("idea:dragEnd", this.model);
        }

        ev.currentTarget.style.opacity = "";
        Ctx.setDraggedAnnotation(null);
        Ctx.setDraggedSegment(null);
        Ctx.draggedIdea = null;
    }

    /**
     * @event
     */
    onDragEnter(ev) {
        // console.log("ideaInIdeaList::onDragEnter() ev: ", ev);
        ev.preventDefault();
    }

    /**
     * @event
     */
    onDragOver(ev) {
        //console.log("ideaInIdeaList::onDragOver() ev: ", ev);
        if (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            IdeaLoom.idea_vent.trigger("idea:dragOver", this.model);
        }

        if (ev.originalEvent) {
            ev = ev.originalEvent;
        }

        if (this.dragOverCounter > 30) {
            this.open();
            //I don't think we should save the state in this case, it's not really user initiated.  benoitg - 2016-01-19
            //this.saveCollapsedState(this.getIsCollapsedState());
        }

        ev.dataTransfer.dropEffect = "move";

        if (Ctx.draggedIdea !== null) {
            // Do nothing if it is the same idea
            if (Ctx.draggedIdea.cid === this.model.cid) {
                ev.dataTransfer.dropEffect = "none";
                return;
            }

            // If it is a descendant, do nothing
            if (this.model.isDescendantOf(Ctx.draggedIdea)) {
                ev.dataTransfer.dropEffect = "none";
                return;
            }

            if (!this.model.userCan(Permissions.ASSOCIATE_IDEA)) {
                ev.dataTransfer.dropEffect = "none";
                return;
            }

            if (ev.target.classList.contains("idealist-abovedropzone")) {
                this.$el.addClass("is-dragover-above");
            } else if (ev.target.classList.contains("idealist-dropzone")) {
                this.$el.addClass("is-dragover-below");
            } else {
                this.$el.addClass("is-dragover");
            }
        } else if (
            Ctx.getDraggedSegment() !== null ||
            Ctx.getDraggedAnnotation() !== null
        ) {
            // extract
            if (!this.model.userCan(Permissions.ASSOCIATE_EXTRACT)) {
                ev.dataTransfer.dropEffect = "none";
                return;
            }
            if (ev.target.classList.contains("idealist-dropzone")) {
                if (!this.model.userCan(Permissions.ADD_IDEA)) {
                    ev.dataTransfer.dropEffect = "none";
                    return;
                }
                this.$el.addClass("is-dragover-below");
            } else {
                this.$el.addClass("is-dragover");
            }
            if (ev.dataTransfer.effectAllowed == "link") {
                ev.dataTransfer.dropEffect = "link";
            } else {
                ev.dataTransfer.dropEffect = "move";
            }
        }

        //We should user a _.debounce instead for performance reasons benoitg 2014-04-13
        this.dragOverCounter += 1;
    }

    /**
     * @event
     * "Finally, the dragleave event will fire at an element when the drag leaves the element. This is the time when you should remove any insertion markers or highlighting. You do not need to cancel this event. [...] The dragleave event will always fire, even if the drag is cancelled, so you can always ensure that any insertion point cleanup can be done during this event." quote https://developer.mozilla.org/en-US/docs/Web/Guide/HTML/Drag_operations
     */
    onDragLeave(ev) {
        //console.log("ideaInIdeaList::onDragLeave() ev: ", ev);

        this.dragOverCounter = 0;
        this.$el.removeClass("is-dragover is-dragover-above is-dragover-below");
    }

    // /!\ The browser will not fire the drop event if, at the end of the last call of the dragenter or dragover event listener (right before the user releases the mouse button), one of these conditions is met:
    // * one of ev.dataTransfer.dropEffect or ev.dataTransfer.effectAllowed is "none"
    // * ev.dataTransfer.dropEffect is not one of the values allowed in ev.dataTransfer.dropEffect
    // "If you don't change the effectAllowed property, then any operation is allowed, just like with the 'all' value. So you don't need to adjust this property unless you want to exclude specific types." quote https://developer.mozilla.org/en-US/docs/Web/Guide/HTML/Drag_operations
    // "During a drag operation, a listener for the dragenter or dragover events can check the effectAllowed property to see which operations are permitted. A related property, dropEffect, should be set within one of these events to specify which single operation should be performed. Valid values for the dropEffect are none, copy, move, or link." quote https://developer.mozilla.org/en-US/docs/Web/API/DataTransfer
    // ev.preventDefault() is also needed here in order to prevent default action (open as link for some elements)
    onDrop(ev) {
        //console.log("ideaInIdeaList::onDrop() ev: ", ev);
        if (Ctx.debugAnnotator) {
            console.log(
                "ideaInIdeaList:onDrop() fired",
                Ctx.getDraggedSegment(),
                Ctx.getDraggedAnnotation()
            );
        }
        if (ev) {
            ev.preventDefault();
        }

        var isDraggedBelow = this.$el.hasClass("is-dragover-below");
        var isDraggedAbove = this.$el.hasClass("is-dragover-above");

        this.$(".idealist-body").trigger("dragleave");

        var segment = Ctx.getDraggedSegment();
        if (segment) {
            if (isDraggedBelow) {
                // Add as a child idea
                this.model.addSegmentAsChild(segment).then((newIdea) => {
                    this._groupContent.setCurrentIdea(newIdea);
                });
            } else {
                // Add to the current idea
                this.model.addSegment(segment);
            }

            Ctx.setDraggedSegment(null);
            return;
        }

        // is this even working?
        var annotation = Ctx.getDraggedAnnotation();
        if (annotation) {
            if (isDraggedBelow) {
                // Add as a child idea
                Ctx.currentAnnotationIdIdea = null;
                Ctx.currentAnnotationNewIdeaParentIdea = this.model;
                Ctx.saveCurrentAnnotationAsExtract();
                // TODO: Should we select that idea? It seems to be done in messageList.@annotationCreated.
                // See if next line can be removed
                this._groupContent.NavigationResetDebateState();
            } else {
                // Add as a segment
                Ctx.currentAnnotationIdIdea = this.model.getId();
                Ctx.currentAnnotationNewIdeaParentIdea = null;
                Ctx.saveCurrentAnnotationAsExtract();
            }

            return;
        }

        if (Ctx.draggedIdea) {
            var idea = Ctx.popDraggedIdea();
            if (idea.cid !== this.model.cid) {
                // If it is a descendent, do nothing
                if (this.model.isDescendantOf(idea)) {
                    return;
                }

                if (isDraggedAbove) {
                    this.model.addSiblingAbove(idea);
                } else if (isDraggedBelow) {
                    this.model.addSiblingBelow(idea);
                } else {
                    this.model.addChild(idea);
                }
            }
        }
    }

    /**
     * Toggle show/hide an item
     * @event
     * @param  {Event} ev
     */
    toggle(ev) {
        //console.log("ideaInIdeaList::toggle()");
        if (ev) {
            ev.preventDefault();
            ev.stopPropagation();
        }

        var analytics = Analytics.getInstance();
        if (this.getIsCollapsedState()) {
            analytics.trackEvent(
                analytics.events.NAVIGATION_TOGGLE_ROOT_IDEA_OPEN
            );
            this.open();
        } else {
            analytics.trackEvent(
                analytics.events.NAVIGATION_TOGGLE_ROOT_IDEA_CLOSE
            );
            this.close();
        }
        // we have just changed the collapsed state by calling open() or close()
        this.saveCollapsedState(this.getIsCollapsedState());
    }

    onIdeaCollaspedStateChange(ev) {
        //console.log("ideaInIdeaList::onIdeaCollaspedStateChange() ev: ", ev, " this:", this);
        if (!this.isDestroyed()) {
            this.applyCustomCollapsedState();
        }
    }

    getCustomCollapsedState() {
        var isCollapsed = undefined;
        if (this.model) {
            var id = this.model.getNumericId();
            if (id) {
                if (this.defaultTableOfIdeasCollapsedState) {
                    var state = this.defaultTableOfIdeasCollapsedState.get(id);
                    if (
                        state == "true" ||
                        state === true ||
                        state == "false" ||
                        state === false
                    ) {
                        isCollapsed = state == "true" || state === true;
                    }
                }
                if (this.tableOfIdeasCollapsedState) {
                    var state = this.tableOfIdeasCollapsedState.get(id);
                    if (
                        state == "true" ||
                        state === true ||
                        state == "false" ||
                        state === false
                    ) {
                        isCollapsed = state == "true" || state === true;
                    }
                }
            }
        }

        return isCollapsed;
    }

    applyCustomCollapsedState() {
        var isCollapsed = this.getCustomCollapsedState();
        // console.log("ideaInIdeaList::applyCustomCollapsedState() idea: ", this.model.getNumericId(), " isCollapsed: ", isCollapsed);
        if (isCollapsed === undefined) {
            isCollapsed = false; // if not set by admin nor user, assume idea is open
        }
        if (isCollapsed) {
            this.close();
        } else {
            this.open();
        }
    }
}

class ideaListIdeaFamilyCollectionView extends Marionette.CollectionView.extend(
    {
        childView: IdeaInIdeaListView,
        /*collectionEvents: {
    'add sync':'render'
  }*/
    }
) {}

export default {
    IdeaFamilyCollectionView: ideaListIdeaFamilyCollectionView,
    IdeaView: IdeaInIdeaListView,
};
