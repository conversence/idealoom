/**
 *
 * @module app.views.groups.panelWrapper
 */

import $ from "jquery";
import Marionette from "backbone.marionette";
import panelViewByPanelSpec from "../../objects/viewsFactory.js";
import Ctx from "../../common/context.js";
import BasePanel from "../basePanel.js";
import i18n from "../../utils/i18n.js";
import panelSpec from "../../models/panelSpec.js";
window.jQuery = $;
import tooltip from "bootstrap-tooltip";
import PanelSpecTypes from "../../utils/panelSpecTypes.js";

/**
 * @class app.views.groups.panelWrapper.PanelWrapper
 */
class PanelWrapper extends Marionette.View.extend({
    template: "#tmpl-panelWrapper",

    regions: {
        contents: ".panelContents",
    },

    panelType: "groupPanel",
    className: "groupPanel",

    modelEvents: {
        "change:hidden": "setHidden",
    },

    ui: {
        title: ".panel-header-title",
        lockPanel: ".js_lockPanel", // clickable zone, which is bigger than just the following icon
        lockPanelIcon: ".js_lockPanel i",
        minimizePanel: ".js_minimizePanel",
        closePanel: ".js_panel-closeButton",
        panelHeader: ".panel-header",
        panelContentsWhenMinimized: ".panelContentsWhenMinimized",
    },

    events: {
        "click @ui.closePanel": "closePanel",
        "click @ui.lockPanel": "toggleLock",
        "click @ui.minimizePanel": "toggleMinimize",
    },

    _unlockCallbackQueue: {},
    panelLockedReason: null,
    panelUnlockedReason: null,
    minPanelSize: BasePanel.prototype.minimized_size,
}) {
    initialize(options) {
        var that = this;
        var contentClass = panelViewByPanelSpec.byPanelSpec(
            options.contentSpec
        );
        this.groupContent = options.groupContent;

        //Shit hack to store the duration as a view variable
        //Some entities will require to know when an animation is completed.
        //TODO: Make fadeIn/fadeOut animation a Promise.
        this.animationDuration = 1000; //milliseconds

        if (!this.groupContent) {
            throw new Error("The groupContent wasn't passed in the options");
        }
        this.contentsView = new contentClass({
            panelWrapper: this,
        });
        Marionette.bindEvents(this, this.model, this.modelEvents);
        this.setPanelMinWidth();
        $(window).on("resize", function () {
            that.setPanelMinWidth();
        });
    }

    onRender() {
        this.showChildView("contents", this.contentsView);
        this.setHidden();
        this.displayContent(true);
        Ctx.initTooltips(this.ui.panelHeader);
        Ctx.initTooltips(this.ui.panelContentsWhenMinimized);
        if (this.model.get("locked")) {
            this.lockPanel(true);
        } else {
            this.unlockPanel(true);
        }
    }

    serializeData() {
        return {
            hideHeader: this.contentsView.hideHeader || false,
            title: this.contentsView.getTitle(),
            tooltip: this.contentsView.tooltip || "",
            headerClass: this.contentsView.headerClass || "",
            userCanChangeUi: Ctx.canUseExpertInterface(),
            hasLock: this.contentsView.lockable,
            hasMinimize:
                this.contentsView.minimizeable ||
                Ctx.getCurrentInterfaceType() === Ctx.InterfaceTypes.EXPERT,
            hasClose: this.contentsView.closeable,
            icon: this.getIcon(),
        };
    }

    /**
     * TODO: refactor this function because the min-width is set also in _panel.scss AND in each panel!!!
     */
    setPanelMinWidth() {
        this.$el.addClass(this.model.attributes.type + "-panel");
        var screenSize = window.innerWidth;
        var isPanelMinimized = this.model.get("minimized");
        if (isPanelMinimized) {
            this.model.set("minWidth", this.minPanelSize);
        } else {
            var isSmallScreen = Ctx.isSmallScreen();
            if (!isSmallScreen) {
                var panelType = this.model.get("type");
                switch (panelType) {
                    case PanelSpecTypes.TABLE_OF_IDEAS.id:
                        this.model.set("minWidth", 350); // 295
                        break;
                    case PanelSpecTypes.NAV_SIDEBAR.id:
                        this.model.set("minWidth", 350);
                        break;
                    case PanelSpecTypes.MESSAGE_LIST.id:
                        this.model.set("minWidth", 500); // 450+offlet
                        break;
                    case PanelSpecTypes.IDEA_PANEL.id:
                        this.model.set("minWidth", 295);
                        break;
                    case PanelSpecTypes.CLIPBOARD.id:
                        this.model.set("minWidth", 270); // 200
                        break;
                    case PanelSpecTypes.SYNTHESIS_EDITOR.id:
                        this.model.set("minWidth", 200);
                        break;
                    case PanelSpecTypes.DISCUSSION_CONTEXT.id:
                        this.model.set("minWidth", 450); // 200?
                        break;
                    case PanelSpecTypes.EXTERNAL_VISUALIZATION_CONTEXT.id:
                        this.model.set("minWidth", 450);
                        break;
                    default:
                        this.model.set("minWidth", 0);
                        break;
                }
            } else {
                this.model.set("minWidth", screenSize);
            }
        }
    }

    /**
     * Change the panel minimization state.  No-op if the state already matches
     * @param {boolean} requestedMiminizedState: Should the panel be minimized
     */
    _changeMinimizePanelsState(requestedMiminizedState) {
        if (requestedMiminizedState === this.model.get("minimized")) {
            return;
        } else {
            this.model.set("minimized", requestedMiminizedState);
            this.setPanelMinWidth();
            this.displayContent();
            this.groupContent.groupContainer.resizeAllPanels();
        }
    }

    toggleMinimize() {
        if (this.model.get("minimized")) {
            this._changeMinimizePanelsState(false);
        } else {
            this._changeMinimizePanelsState(true);
        }
    }

    unminimizePanel(evt) {
        this._changeMinimizePanelsState(false);
    }

    minimizePanel(evt) {
        this._changeMinimizePanelsState(true);
    }

    displayContent(skipAnimation) {
        //var animationDuration = 1000;
        var animationDuration = this.animationDuration;
        var that = this;
        var isPanelMinimized = this.model.get("minimized");
        if (isPanelMinimized) {
            this.$(".panel-header-minimize i")
                .addClass("icon-arrowright")
                .removeClass("icon-arrowleft");
            this.$(".panel-header-minimize").attr(
                "data-original-title",
                i18n.gettext("Maximize panel")
            );
            if (skipAnimation) {
                this.$el.addClass("minSizeGroup");
            } else {
                this.$el
                    .find(".panelContentsWhenMinimized > span")
                    .delay(animationDuration * 0.6)
                    .fadeIn(animationDuration * 0.3);
                this.$el
                    .find(".panelContents")
                    .fadeOut(animationDuration * 0.9);
                this.$el
                    .find("header span.panel-header-title")
                    .fadeOut(animationDuration * 0.4);
                this.$el
                    .children(".panelContentsWhenMinimized")
                    .delay(animationDuration * 0.6)
                    .fadeIn(animationDuration * 0.4);
            }
        } else {
            this.$(".panel-header-minimize i")
                .addClass("icon-arrowleft")
                .removeClass("icon-arrowright");
            this.$(".panel-header-minimize").attr(
                "data-original-title",
                i18n.gettext("Minimize panel")
            );
            if (skipAnimation) {
                this.$el.removeClass("minSizeGroup");
            } else {
                this.$el
                    .find(".panelContentsWhenMinimized > span")
                    .fadeOut(animationDuration * 0.3);
                this.$el
                    .find(".panelContents")
                    .delay(animationDuration * 0.2)
                    .fadeIn(animationDuration * 0.8);
                this.$el
                    .find("header span.panel-header-title")
                    .delay(animationDuration * 0.5)
                    .fadeIn(animationDuration * 0.5);
                this.$el
                    .children(".panelContentsWhenMinimized")
                    .fadeOut(animationDuration * 0.3);
            }
        }
    }

    resetTitle(newTitle) {
        this.ui.title.html(newTitle);
    }

    closePanel() {
        Ctx.removeCurrentlyDisplayedTooltips();
        this.model.collection.remove(this.model);
    }

    setHidden() {
        if (this.model.get("hidden")) {
            this.$el.hide();
        } else {
            this.$el.css(
                "display",
                "table-cell"
            ); /* Set it back to its original value, which is "display: table-cell" in _groupContainer.scss . But why is it so? */
        }
        this.groupContent.groupContainer.resizeAllPanels(true);
    }

    /**
     * lock the panel if unlocked
     */
    lockPanel(force) {
        if (force || !this.model.get("locked")) {
            this.model.set("locked", true);
            this.ui.lockPanelIcon
                .addClass("icon-lock")
                .removeClass("icon-lock-open")
                .attr("data-original-title", i18n.gettext("Unlock panel"));
        }
    }

    /**
     * @param {boolean} locking: True if we want to lock the panel. False if we want to unlock it
     * @param {boolean} informUser: Show a tooltip next to the lock icon, informing the user that the panel has been autolocked.
     * @param {string} reason: The reason why the panel will be automatically locked. Possible values: undefined, "USER_IS_WRITING_A_MESSAGE", "USER_WAS_WRITING_A_MESSAGE"
     **/
    autoLockOrUnlockPanel(locking, informUser, reason) {
        var that = this;
        informUser = informUser === undefined ? true : informUser;
        locking = locking === undefined ? true : locking;
        reason = reason === undefined ? null : reason;
        var needsToChange =
            (locking && !this.model.get("locked")) ||
            (!locking && this.model.get("locked"));
        if (needsToChange) {
            if (locking) this.lockPanel();
            else this.unlockPanel();
            if (locking) that.panelLockedReason = reason;
            else that.panelUnlockedReason = reason;
            if (informUser) {
                // show a special tooltip
                setTimeout(function () {
                    var el = that.ui.lockPanelIcon;
                    var initialTitle = el.attr("data-original-title");

                    if (locking && reason == "USER_IS_WRITING_A_MESSAGE") {
                        el.attr(
                            "data-original-title",
                            i18n.gettext(
                                "We have locked the panel for you, so its content won't change while you're writing your message. Click here to unlock"
                            )
                        );
                    } else if (
                        !locking &&
                        reason == "USER_WAS_WRITING_A_MESSAGE"
                    ) {
                        el.attr(
                            "data-original-title",
                            i18n.gettext(
                                "We have unlocked the panel for you, so its content can change now that you're not writing a message anymore. Click here to lock it back"
                            )
                        );
                    } else {
                        if (locking) {
                            el.attr(
                                "data-original-title",
                                i18n.gettext(
                                    "We have locked the panel for you. Click here to unlock"
                                )
                            );
                        } else {
                            el.attr(
                                "data-original-title",
                                i18n.gettext(
                                    "We have unlocked the panel for you. Click here to lock it back"
                                )
                            );
                        }
                    }
                    el.tooltip("destroy");
                    el.tooltip({
                        container: Ctx.getTooltipsContainerSelector(),
                        placement: "left",
                    });
                    el.tooltip("show");
                    setTimeout(function () {
                        el.attr("data-original-title", initialTitle);
                        el.tooltip("destroy");
                        el.tooltip({
                            container: Ctx.getTooltipsContainerSelector(),
                        });
                    }, 7000);
                }, 5000); // FIXME: if we set this timer lower than this, the tooltip shows and immediately disappears. Why?
            }
        }
    }

    /**
     * @param {boolean} informUser: Show a tooltip next to the lock icon, informing the user that the panel has been autolocked.
     * @param {string} reason: The reason why the panel will be automatically locked. Possible values: undefined, "USER_IS_WRITING_A_MESSAGE"
     **/
    autoLockPanel(informUser, reason) {
        this.autoLockOrUnlockPanel(true, informUser, reason);
    }

    /**
     * @param {boolean} informUser: bool. Show a tooltip next to the lock icon, informing the user that the panel has been autounlocked.
     * @param {string} reason: The reason why the panel will be automatically unlocked. Possible values: undefined, "USER_WAS_WRITING_A_MESSAGE"
     **/
    autoUnlockPanel(informUser, reason) {
        this.autoLockOrUnlockPanel(false, informUser, reason);
    }

    /**
     * unlock the panel if locked
     */
    unlockPanel(force) {
        if (force || this.model.get("locked")) {
            this.model.set("locked", false);
            this.ui.lockPanelIcon
                .addClass("icon-lock-open")
                .removeClass("icon-lock lockedGlow")
                .attr("data-original-title", i18n.gettext("Lock panel"));

            if (_.size(this._unlockCallbackQueue) > 0) {
                //console.log("Executing queued callbacks in queue: ",this.unlockCallbackQueue);
                _.each(this._unlockCallbackQueue, function (callback) {
                    callback();
                });
                //We presume the callbacks have their own calls to render
                this._unlockCallbackQueue = {};
            }
        }
    }

    /**
     * Toggle the lock state of the panel
     */
    toggleLock() {
        console.log("toggleLock()");
        if (this.isPanelLocked()) {
            console.log("panel was locked, so we unlock it");
            this.unlockPanel(true);
        } else {
            console.log("panel was unlocked, so we lock it");
            this.lockPanel(true);
        }
    }

    isPanelLocked() {
        return this.model.get("locked");
    }

    getPanelLockedReason() {
        return this.panelLockedReason;
    }

    getPanelUnlockedReason() {
        return this.panelUnlockedReason;
    }

    isPanelMinimized() {
        return this.model.get("minimized");
    }

    isPanelHidden() {
        return this.model.get("hidden");
    }

    /**
     * Process a callback that can be inhibited by panel locking.
     * If the panel is unlocked, the callback will be called immediately.
     * If the panel is locked, visual notifications will be shown, and the
     * callback will be memorized in a queue, removing duplicates.
     * Callbacks receive no parameters.
     * If queued, they must assume that they can be called at a later time,
     * and have the means of getting any updated information they need.
     */
    filterThroughPanelLock(callback, queueWithId) {
        if (!this.model.get("locked")) {
            callback();
            this.ui.lockPanel.children().removeClass("lockedGlow");
        } else {
            this.ui.lockPanel.children().addClass("lockedGlow");

            if (queueWithId) {
                if (this._unlockCallbackQueue[queueWithId] !== undefined) {
                } else {
                    this._unlockCallbackQueue[queueWithId] = callback;
                }
            }
        }
    }

    getIcon() {
        var type = this.contentsView.panelType;
        var icon = "";
        switch (type.id) {
            case PanelSpecTypes.IDEA_PANEL.id:
                icon = "icon-idea";
                break;
            case PanelSpecTypes.NAV_SIDEBAR.id:
                icon = "icon-home";
                break;
            case PanelSpecTypes.MESSAGE_LIST.id:
                icon = "icon-comment";
                break;
            case PanelSpecTypes.CLIPBOARD.id:
                // ne need because of resetTitle - segment
                icon = "icon-clipboard";
                break;
            case PanelSpecTypes.SYNTHESIS_EDITOR.id:
                icon = "icon-doc";
                break;
            case PanelSpecTypes.DISCUSSION_CONTEXT.id:
                break;
            case PanelSpecTypes.TABLE_OF_IDEAS.id:
                icon = "icon-discuss";
                break;
            default:
                break;
        }
        return icon;
    }
}

export default PanelWrapper;
