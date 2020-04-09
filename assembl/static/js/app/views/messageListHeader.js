/**
 *
 * @module app.views.messageListHeader
 */

import Backbone from "backbone";

import Raven from "raven-js";
import _ from "underscore";
import $ from "jquery";
import Ctx from "../common/context.js";
import dropdown from "bootstrap-dropdown";
import IdeaLoom from "../app.js";
import FlipSwitchButtonModel from "../models/flipSwitchButton.js";
import FlipSwitchButtonView from "./flipSwitchButton.js";
import i18n from "../utils/i18n.js";
import Permissions from "../utils/permissions.js";
import PanelSpecTypes from "../utils/panelSpecTypes.js";
import BasePanel from "./basePanel.js";
import Marionette from "backbone.marionette";
import CollectionManager from "../common/collectionManager.js";
import Promise from "bluebird";

/**
 * Constants
 */
var DEFAULT_MESSAGE_VIEW_LI_ID_PREFIX = "js_defaultMessageView-";

var MESSAGE_LIST_VIEW_STYLES_CLASS_PREFIX = "js_messageList-view-";

class MessageListHeader extends Marionette.View.extend({
    template: "#tmpl-messageListHeader",
    className: "messageListHeaderItsMe",

    ui: {
        queryInfo: ".messageList-query-info",
        expertViewToggleButton: ".show-expert-mode-toggle-button",
        viewStyleDropdown: ".js_messageListViewStyle-dropdown",
        defaultMessageViewDropdown: ".js_defaultMessageView-dropdown",
        filtersDropdown: ".js_filters-dropdown",
    },
}) {
    initialize(options) {
        //console.log("MessageListHeader::initialize(options)", options);
        var that = this;

        this.options = options;
        this.ViewStyles = options.ViewStyles;
        this.messageList = options.messageList;
        this.defaultMessageStyle = options.defaultMessageStyle;
        this.expertViewIsAvailable = options.expertViewIsAvailable;
        this.isUsingExpertView = options.isUsingExpertView;
        this.currentViewStyle = options.currentViewStyle;
        this.currentQuery = options.currentQuery;

        this.toggleButtonModelInstance = new FlipSwitchButtonModel({
            labelOn: "on", // TODO: i18n
            labelOff: "off", // TODO: i18n
            isOn: this.isUsingExpertView,
        });
        this.toggleButtonModelInstance.on("change:isOn", function () {
            //console.log("messageListHeader got the change:isOn event");
            that.toggleExpertView();
        });

        this.delegateEvents(this._generateEvents());
    }

    _generateEvents() {
        var that = this;
        var data = {
            //'click @ui.expertViewToggleButton': 'toggleExpertView' // handled by change:isOn model event instead
            "click .js_deleteFilter ": "onFilterDeleteClick",
        };

        _.each(this.ViewStyles, function (messageListViewStyle) {
            var key = "click ." + messageListViewStyle.css_class;
            data[key] = "onSelectMessageListViewStyle";
        });

        _.each(Ctx.AVAILABLE_MESSAGE_VIEW_STYLES, function (messageViewStyle) {
            var key =
                "click ." + that.getMessageViewStyleCssClass(messageViewStyle);
            data[key] = "onSelectDefaultMessageViewStyle";
        });

        _.each(this.messageList.currentQuery.availableFilters, function (
            availableFilterDef
        ) {
            var candidateFilter = new availableFilterDef();
            if (_.isFunction(candidateFilter.getImplicitValuePromise)) {
                var key = "click ." + candidateFilter.getAddButtonCssClass();
                data[key] = "onAddFilter";
            }
        });

        //console.log(data);
        return data;
    }

    serializeData() {
        return {
            expertViewIsAvailable: this.expertViewIsAvailable,
            isUsingExpertView: this.isUsingExpertView,
            availableViewStyles: this.ViewStyles,
            Ctx: Ctx,
            currentViewStyle: this.currentViewStyle,
        };
    }

    onRender() {
        this.renderMessageListViewStyleDropdown();
        this.renderDefaultMessageViewDropdown();
        this.renderMessageListFiltersDropdown();
        this.renderToggleButton();

        if (!this.isUsingExpertView) {
            this.renderUserViewButtons();
        }

        this.renderQueryInfo();
        Ctx.initTooltips(this.$el);
        IdeaLoom.tour_vent.trigger("requestTour", "message_list_options");
    }

    renderToggleButton() {
        //console.log("messageListHeader::renderToggleButton()");
        // check that ui is here (it may not be, for example if logged out). I could not use a region here because the region would not always have been present in DOM, which is not possible
        var el = this.ui.expertViewToggleButton;
        if (el && this.expertViewIsAvailable) {
            var v = new FlipSwitchButtonView({
                model: this.toggleButtonModelInstance,
            });
            el.html(v.render().el);
        }
    }

    toggleExpertView() {
        //console.log("messageListHeader::toggleExpertView()");
        this.isUsingExpertView = !this.isUsingExpertView;
        this.messageList.triggerMethod(
            "setIsUsingExpertView",
            this.isUsingExpertView
        );

        // TODO: avoid waiting for the end of animation, by re-rendering only the content (region?) on the left (not this button)
        var that = this;
        setTimeout(function () {
            that.render();
        }, 500);
    }

    /**
     * Renders the messagelist view style dropdown button
     */
    renderMessageListViewStyleDropdown() {
        var that = this;
        var html = "";

        html +=
            '<a href="#" class="dropdown-toggle" data-toggle="dropdown" aria-expanded="false">';
        html += this.currentViewStyle.label;
        html += '<span class="icon-arrowdown"></span></a>';
        html += '<ul class="dropdown-menu">';
        _.each(this.ViewStyles, function (messageListViewStyle) {
            html +=
                '<li><a class="' +
                messageListViewStyle.css_class +
                '">' +
                messageListViewStyle.label +
                "</a></li>";
        });
        html += "</ul>";
        this.ui.viewStyleDropdown.html(html);
    }

    /**
     * Renders the messagelist view style dropdown button
     */
    renderMessageListFiltersDropdown() {
        var that = this;
        var filtersPromises = [];

        _.each(this.messageList.currentQuery.availableFilters, function (
            availableFilterDef
        ) {
            var candidateFilter = new availableFilterDef();
            var implicitValuePromise = undefined;
            if (_.isFunction(candidateFilter.getImplicitValuePromise)) {
                implicitValuePromise = candidateFilter.getImplicitValuePromise();
                if (implicitValuePromise !== undefined) {
                    filtersPromises.push(
                        Promise.join(
                            candidateFilter.getLabelPromise(),
                            implicitValuePromise,
                            function (label, value) {
                                if (value !== undefined) {
                                    return (
                                        '<li><a class="' +
                                        candidateFilter.getAddButtonCssClass() +
                                        '" data-filterid="' +
                                        candidateFilter.getId() +
                                        '" data-toggle="tooltip" title="" data-placement="left" data-original-title="' +
                                        candidateFilter.getHelpText() +
                                        '">' +
                                        label +
                                        "</a></li>"
                                    );
                                } else {
                                    return "";
                                }
                            }
                        )
                    );
                }
            }
        });
        Promise.all(filtersPromises).then(function (filterButtons) {
            var html = "";
            html +=
                '<a href="#" class="dropdown-toggle" data-toggle="dropdown" aria-expanded="false">';
            html += i18n.gettext("Add filter");
            html += '<span class="icon-arrowdown"></span></a>';
            html += '<ul class="dropdown-menu">';
            html += filterButtons.join("");
            html += "</ul>";
            that.ui.filtersDropdown.html(html);
            Ctx.initTooltips(that.$el);
        });
    }

    /**
     * get a view style css_class
     * @param messageViewStyle
     * @returns {string}
     */
    getMessageViewStyleCssClass(messageViewStyle) {
        return DEFAULT_MESSAGE_VIEW_LI_ID_PREFIX + messageViewStyle.id;
    }

    /**
     * get a view style definition by id
     * @param {messageViewStyle.id} messageListViewStyleClass
     * @returns {messageViewStyle | undefined}
     */
    getMessageListViewStyleDefByCssClass(messageListViewStyleClass) {
        return _.find(this.ViewStyles, function (viewStyle) {
            return viewStyle.css_class == messageListViewStyleClass;
        });
    }

    /**
     * get a view style definition by id
     * @param {messageViewStyle.id} messageViewStyleClass
     * @returns {messageViewStyle | undefined}
     */
    getMessageViewStyleDefByCssClass(messageViewStyleClass) {
        var that = this;
        return _.find(Ctx.AVAILABLE_MESSAGE_VIEW_STYLES, function (
            messageViewStyle
        ) {
            return (
                that.getMessageViewStyleCssClass(messageViewStyle) ==
                messageViewStyleClass
            );
        });
    }

    /**
     * @event
     */
    onSelectMessageListViewStyle(e) {
        //console.log("messageListHeader::onSelectMessageListViewStyle()");
        var messageListViewStyleClass;

        var messageListViewStyleSelected;
        var classes = $(e.currentTarget).attr("class").split(" ");
        messageListViewStyleClass = _.find(classes, function (cls) {
            return cls.indexOf(MESSAGE_LIST_VIEW_STYLES_CLASS_PREFIX) === 0;
        });
        var messageListViewStyleSelected = this.getMessageListViewStyleDefByCssClass(
            messageListViewStyleClass
        );

        this.messageList.setViewStyle(messageListViewStyleSelected);
        this.messageList.render();
    }

    /**
     * @event
     */
    onSelectDefaultMessageViewStyle(e) {
        var classes = $(e.currentTarget).attr("class").split(" ");
        var defaultMessageListViewStyleClass;
        defaultMessageListViewStyleClass = _.find(classes, function (cls) {
            return cls.indexOf(DEFAULT_MESSAGE_VIEW_LI_ID_PREFIX) === 0;
        });
        var messageViewStyleSelected = this.getMessageViewStyleDefByCssClass(
            defaultMessageListViewStyleClass
        );

        this.defaultMessageStyle = messageViewStyleSelected;
        this.messageList.triggerMethod(
            "setDefaultMessageStyle",
            messageViewStyleSelected
        );

        //this.setIndividualMessageViewStyleForMessageListViewStyle(messageViewStyleSelected);
        this.messageList.triggerMethod(
            "setIndividualMessageViewStyleForMessageListViewStyle",
            messageViewStyleSelected
        );

        this.renderDefaultMessageViewDropdown();
    }

    /**
     * @event
     */
    onAddFilter(ev) {
        var that = this;
        var filterId = ev.currentTarget.getAttribute("data-filterid");
        var filterDef = this.messageList.currentQuery.getFilterDefById(
            filterId
        );
        var filter = new filterDef();
        var queryChanged = false;

        var execute = function (value) {
            queryChanged = that.messageList.currentQuery.addFilter(
                filterDef,
                value
            );
            if (queryChanged) {
                that.messageList.render();
            }
        };

        var should_ask_value_from_user =
            "should_ask_value_from_user" in filterDef
                ? filterDef.should_ask_value_from_user
                : false;
        if (
            should_ask_value_from_user &&
            "askForValue" in filter &&
            _.isFunction(filter.askForValue)
        ) {
            filter.askForValue();
            filter.getImplicitValuePromise().then(function (implicitValue) {
                if (implicitValue) {
                    that.messageList.currentQuery.clearFilter(filterDef);
                    execute(implicitValue);
                }
            });
        } else {
            filter.getImplicitValuePromise().then(function (implicitValue) {
                execute(implicitValue);
            });
        }
    }

    /**
     * @event
     */
    onFilterDeleteClick(ev) {
        //console.log("MessageListHeader:onFilterDeleteClick(ev)", ev);
        var valueIndex = ev.currentTarget.getAttribute("data-value-index");
        var filterid = ev.currentTarget.getAttribute("data-filterid");
        var filter = this.currentQuery.getFilterDefById(filterid);
        this.currentQuery.clearFilter(filter, valueIndex);
        this.messageList.render();
    }

    /**
     * Renders the default message view style dropdown button
     */
    renderDefaultMessageViewDropdown() {
        var that = this;
        var html = "";

        html +=
            '<a href="#" class="dropdown-toggle" data-toggle="dropdown" aria-expanded="false">';
        html += this.defaultMessageStyle.label;
        html += '<span class="icon-arrowdown"></span></a>';
        html += '<ul class="dropdown-menu">';
        _.each(Ctx.AVAILABLE_MESSAGE_VIEW_STYLES, function (messageViewStyle) {
            html +=
                '<li><a class="' +
                that.getMessageViewStyleCssClass(messageViewStyle) +
                '">' +
                messageViewStyle.label +
                "</a></li>";
        });
        html += "</ul>";
        this.ui.defaultMessageViewDropdown.html(html);
    }

    /**
     * Renders the search result information
     */
    renderUserViewButtons() {
        var that = this;
        var resultNumTotal;
        var resultNumUnread;

        _.each(this.ViewStyles, function (viewStyle) {
            if (that.currentViewStyle === viewStyle) {
                that.$("." + viewStyle.css_class).addClass("selected");
            } else {
                that.$("." + viewStyle.css_class).removeClass("selected");
            }
        });

        //this.currentQuery.getResultNumTotal() === undefined ? resultNumTotal = '' : resultNumTotal = i18n.sprintf("%d", this.currentQuery.getResultNumTotal());
        this.$("." + this.ViewStyles.THREADED.css_class).html(
            this.ViewStyles.THREADED.label
        );

        this.$("." + this.ViewStyles.RECENTLY_ACTIVE_THREADS.css_class).html(
            this.ViewStyles.RECENTLY_ACTIVE_THREADS.label
        );
        //this.currentQuery.getResultNumUnread() === undefined ? resultNumUnread = '' : resultNumUnread = i18n.sprintf("%d", this.currentQuery.getResultNumUnread());

        this.$("." + this.ViewStyles.NEW_MESSAGES.css_class).html(
            this.ViewStyles.NEW_MESSAGES.label
        );
        this.$("." + this.ViewStyles.REVERSE_CHRONOLOGICAL.css_class).html(
            this.ViewStyles.REVERSE_CHRONOLOGICAL.label
        );
        this.$("." + this.ViewStyles.CHRONOLOGICAL.css_class).html(
            this.ViewStyles.CHRONOLOGICAL.label
        );
        this.$("." + this.ViewStyles.POPULARITY.css_class).html(
            this.ViewStyles.POPULARITY.label
        );
    }

    /**
     * Renders the search result information
     */
    renderQueryInfo() {
        var that = this;
        this.currentQuery
            .getHtmlDescriptionPromise()
            .then(function (htmlDescription) {
                that.ui.queryInfo.html(htmlDescription);
            });
    }
}

export default MessageListHeader;
