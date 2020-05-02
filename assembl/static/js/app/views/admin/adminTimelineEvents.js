/**
 *
 * @module app.views.admin.adminTimelineEvents
 */

import IdeaLoom from "../../app.js";

import Ctx from "../../common/context.js";
import i18n from "../../utils/i18n.js";
import EditableField from "../reusableDataFields/editableField.js";
import TimelineEvent from "../../models/timeline.js";
import LangString from "../../models/langstring.js";
import CollectionManager from "../../common/collectionManager.js";
import { View, CollectionView } from "backbone.marionette";
import Growl from "../../utils/growl.js";
import SimpleLangStringEditPanel from "../simpleLangStringEdit.js";
import Moment from "moment";
import AdminNavigationMenu from "./adminNavigationMenu.js";
import $ from "jquery";
import _ from "underscore";
import LoaderView from "../loaderView.js";
import Promise from "bluebird";

/**
 * @class  app.views.admin.adminTimelineEvents.AdminTimelineEventPanel
 */
class AdminTimelineEventPanel extends LoaderView.extend({
    template: "#tmpl-adminTimelineEvents",

    ui: {
        addTimelineEvent: ".js_add_event",
        save: ".js_save",
        timelineEventsList: ".js_timelineEventsList",
        navigationMenuHolder: ".navigation-menu-holder",
    },

    regions: {
        timelineEventsList: "@ui.timelineEventsList",
        navigationMenuHolder: "@ui.navigationMenuHolder",
    },

    events: {
        "click @ui.addTimelineEvent": "addTimelineEvent",
    },
}) {
    initialize(options) {
        var that = this;
        var collectionManager = new CollectionManager();
        this.timelineEventCollection = null;
        this.setLoading(true);
        if (this.isDestroyed()) {
            return;
        }
        this.timelinePromise = collectionManager
            .getAllTimelineEventCollectionPromise()
            .then(function (timeline) {
                that.timelineEventCollection = timeline;
                that.setLoading(false);
                that.render();
            });
    }

    addTimelineEvent(ev) {
        var eventCollection = this.timelineEventCollection;
        var lastEventId;
        var event;
        var title = new LangString.Model();
        var titles = {};
        var description = new LangString.Model();
        var descriptions = {};
        var preferences = Ctx.getPreferences();
        if (eventCollection.length > 0) {
            lastEventId = eventCollection.models[eventCollection.length - 1].id;
        }
        _.map(preferences.preferred_locales, function (loc) {
            titles[loc] = "";
            descriptions[loc] = "";
        });
        title.initFromDict(titles);
        description.initFromDict(titles);
        event = new TimelineEvent.Model({
            title: title,
            description: description,
            previous_event: lastEventId,
        });
        eventCollection.add(event);
        event.save(null, {
            parse: true,
            success: function () {
                // rerender so the langstring ids are up to date
                eventCollection.render();
            },
        });
        ev.preventDefault();
    }

    serializeData() {
        return {};
    }

    onRender() {
        if (this.isDestroyed() || this.isLoading()) {
            return;
        }
        if (this.timelineEventCollection != null) {
            this.showChildView(
                "timelineEventsList",
                new TimelineEventsList({
                    basePanel: this,
                    collection: this.timelineEventCollection,
                })
            );
        }
        var menu = new AdminNavigationMenu.discussionAdminNavigationMenu({
            selectedSection: "timeline",
        });
        this.getRegion("navigationMenuHolder").show(menu);
    }
}

/**
 * @class  app.views.admin.adminTimelineEvents.TimelineEventView
 */
class TimelineEventView extends View.extend({
    template: "#tmpl-adminTimelineEvent",

    ui: {
        eventTitle: ".js_timeline_title",
        eventDescription: ".js_timeline_description",
        eventImageUrl: ".js_timeline_image_url",
        eventIdentifier: ".js_identifier",
        eventStartDate: ".js_start_date",
        eventEndDate: ".js_end_date",
        eventUp: ".js_timeline_up",
        eventDown: ".js_timeline_down",
        eventDelete: ".js_timeline_delete",
    },

    regions: {
        eventTitle: "@ui.eventTitle",
        eventDescription: "@ui.eventDescription",
    },

    events: {
        "click @ui.eventUp": "reorderColumnUp",
        "click @ui.eventDown": "reorderColumnDown",
        "click @ui.eventDelete": "deleteColumn",
        "change @ui.eventImageUrl": "changeImageUrl",
        "change @ui.eventIdentifier": "changeIdentifier",
        "change @ui.eventStartDate": "changeStartDate",
        "change @ui.eventEndDate": "changeEndDate",
    },
}) {
    getIndex() {
        return _.indexOf(this.model.collection.models, this.model);
    }

    serializeData() {
        return {
            event: this.model,
            index: this.getIndex(),
            collsize: this.model.collection.length,
        };
    }

    onRender() {
        this.showChildView(
            "eventTitle",
            new SimpleLangStringEditPanel({
                model: this.model.get("title"),
                owner_relative_url: this.model.url() + "/title",
            })
        );
        this.showChildView(
            "eventDescription",
            new SimpleLangStringEditPanel({
                model: this.model.get("description"),
                owner_relative_url: this.model.url() + "/description",
            })
        );
    }

    reorderColumnDown(ev) {
        var index = this.getIndex();
        var nextModel = this.model.collection.at(index + 1);
        Promise.resolve(
            $.ajax(nextModel.url() + "/reorder_up", {
                method: "POST",
            })
        ).then(function (data) {
            nextModel.collection.fetch({
                success: function () {
                    nextModel.collection.sort();
                },
            });
        });
        ev.preventDefault();
    }

    reorderColumnUp(ev) {
        var model = this.model;
        Promise.resolve(
            $.ajax(model.url() + "/reorder_up", {
                method: "POST",
            })
        ).then(function (data) {
            model.collection.fetch({
                success: function () {
                    model.collection.sort();
                },
            });
        });
        ev.preventDefault();
    }

    deleteColumn(ev) {
        var nextModel = null;
        var prevColumn = this.model.get("previous_event");
        var index = this.getIndex();
        if (index + 1 < this.model.collection.length) {
            nextModel = this.model.collection.at(index + 1);
        }
        this.model.destroy({
            success: function () {
                if (nextModel !== null) {
                    // update the previous_event value
                    nextModel.fetch();
                }
            },
        });
        ev.preventDefault();
    }

    changeImageUrl(ev) {
        this.model.set("image_url", ev.currentTarget.value);
        this.model.save();
        ev.preventDefault();
    }

    changeIdentifier(ev) {
        this.model.set("identifier", ev.currentTarget.value);
        this.model.save();
        ev.preventDefault();
    }

    checkDate(date) {
        var date = Moment(date);
        if (date.isValid()) {
            return date.utc().format();
        }
    }

    changeStartDate(ev) {
        var date = this.checkDate(ev.currentTarget.value);
        if (date != undefined) {
            this.model.set("start", date);
            this.model.save();
        } else {
            Growl.showBottomGrowl(
                Growl.GrowlReason.ERROR,
                i18n.gettext("Invalid date and time")
            );
        }
        ev.preventDefault();
    }

    changeEndDate(ev) {
        var date = this.checkDate(ev.currentTarget.value);
        if (date != undefined) {
            this.model.set("end", date);
            this.model.save();
        } else {
            Growl.showBottomGrowl(
                Growl.GrowlReason.ERROR,
                i18n.gettext("Invalid date and time")
            );
        }
        ev.preventDefault();
    }
}

/**
 * The collections of events to be seen on this idea
 * @class app.views.adminTimelineEvents.TimelineEventsList
 */
class TimelineEventsList extends CollectionView.extend({
    childView: TimelineEventView,
}) {
    initialize(options) {
        this.options = options;
    }
}

export default AdminTimelineEventPanel;
