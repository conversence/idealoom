/**
 *
 * @module app.views.announcements
 */

import { View, CollectionView } from "backbone.marionette";

import _ from "underscore";
import $ from "jquery";
import Promise from "bluebird";
import i18n from "../utils/i18n.js";
import IdeaLoom from "../app.js";
import Ctx from "../common/context.js";
import CollectionManager from "../common/collectionManager.js";
import Types from "../utils/types.js";
import Announcement from "../models/announcement.js";
import AgentViews from "./agent.js";
import LoaderView from "./loaderView.js";
import EditableLSField from "./reusableDataFields/editableLSField.js";
import CKEditorLSField from "./reusableDataFields/ckeditorLSField.js";
import TrueFalseField from "./reusableDataFields/trueFalseField.js";

/**
 */
class AbstractAnnouncementView extends LoaderView.extend({
    events: {},

    regions: {
        region_title: ".js_announcement_title_region",
        region_body: ".js_announcement_body_region",
        region_shouldPropagateDown:
            ".js_announcement_shouldPropagateDown_region",
    },

    modelEvents: {
        change: "render",
    },
}) {
    initialize(options) {}

    onRender() {
        Ctx.removeCurrentlyDisplayedTooltips(this.$el);
        Ctx.initTooltips(this.$el);
    }
}

class AnnouncementView extends AbstractAnnouncementView.extend({
    template: "#tmpl-announcement",
    className: "attachment",
}) {}

class AnnouncementMessageView extends AbstractAnnouncementView.extend({
    template: "#tmpl-announcementMessage",

    attributes: {
        class: "announcementMessage bx",
    },

    regions: {
        authorAvatarRegion: ".js_author_avatar_region",
        authorNameRegion: ".js_author_name_region",
    },

    modelEvents: {
        change: "render",
    },
}) {
    serializeData() {
        if (this.isLoading()) {
            return {};
        }
        var retval = this.model.toJSON();
        retval.creator = this.creator;
        retval.ctx = Ctx;
        retval.hide_creator = this.hideCreator;
        if (retval.body) {
            retval.body = retval.body.bestValue(this.translationData);
        }
        if (retval.title) {
            retval.title = retval.title.bestValue(this.translationData);
        }
        return retval;
    }

    initialize(options) {
        var that = this;
        var collectionManager = new CollectionManager();
        this.setLoading(true);
        this.hideCreator = options.hide_creator;
        this.creator = undefined;
        Promise.join(
            this.model.getCreatorPromise(),
            collectionManager.getUserLanguagePreferencesPromise(Ctx),
            function (creator, ulp) {
                if (!that.isDestroyed()) {
                    that.translationData = ulp;
                    that.creator = creator;
                    that.setLoading(false);
                    that.render();
                }
            }
        );
    }

    onRender() {
        AbstractAnnouncementView.prototype.onRender.call(this);
        if (!this.hideCreator && !this.isLoading()) {
            this.renderCreator();
        }
    }

    renderCreator() {
        var agentAvatarView = new AgentViews.AgentAvatarView({
            model: this.creator,
            avatarSize: 50,
        });
        this.showChildView("authorAvatarRegion", agentAvatarView);
        var agentNameView = new AgentViews.AgentNameView({
            model: this.creator,
        });
        this.showChildView("authorNameRegion", agentNameView);
    }
}

class AnnouncementEditableView extends AbstractAnnouncementView.extend({
    template: "#tmpl-announcementEditable",
    className: "announcementEditable",

    events: _.extend({}, AbstractAnnouncementView.prototype.events, {
        "click .js_announcement_delete": "onDeleteButtonClick", //Dynamically rendered, do NOT use @ui
    }),
}) {
    initialize(options) {
        var that = this;
        var collectionManager = new CollectionManager();
        this.setLoading(true);
        collectionManager
            .getUserLanguagePreferencesPromise(Ctx)
            .then(function (ulp) {
                if (!that.isDestroyed()) {
                    that.translationData = ulp;
                    that.setLoading(false);
                    that.render();
                }
            });
    }

    onRender() {
        if (this.isLoading()) {
            return;
        }
        AbstractAnnouncementView.prototype.onRender.call(this);

        var titleView = new EditableLSField({
            model: this.model,
            modelProp: "title",
            translationData: this.translationData,
            placeholder: i18n.gettext(
                "Please give a title of this announcement..."
            ),
        });
        this.showChildView("region_title", titleView);

        var bodyView = new CKEditorLSField({
            model: this.model,
            modelProp: "body",
            translationData: this.translationData,
            placeholder: i18n.gettext(
                "Please write the content of this announcement here..."
            ),
        });
        this.showChildView("region_body", bodyView);

        var shouldPropagateDownView = new TrueFalseField({
            model: this.model,
            modelProp: "should_propagate_down",
        });
        this.showChildView(
            "region_shouldPropagateDown",
            shouldPropagateDownView
        );
    }

    onDeleteButtonClick(ev) {
        this.model.destroy();
    }
}

class AnnouncementListEmptyEditableView extends View.extend({
    template: "#tmpl-announcementListEmptyEditable",

    ui: {
        addAnnouncementButton: ".js_announcementAddButton",
    },

    events: {
        "click @ui.addAnnouncementButton": "onAddAnnouncementButtonClick",
    },
}) {
    initialize(options) {
        //console.log(options);
        this.objectAttachedTo = options.objectAttachedTo;
        this.collection = options.collection;
    }

    onAddAnnouncementButtonClick(ev) {
        var announcement = new Announcement.Model({
            "@type": Types.IDEA_ANNOUNCEMENT,
            creator: Ctx.getCurrentUser().id,
            last_updated_by: Ctx.getCurrentUser().id,
            idObjectAttachedTo: this.objectAttachedTo.id,
            should_propagate_down: true,
        });
        this.collection.add(announcement);
        announcement.save();
    }
}

class AnnouncementEditableCollectionView extends CollectionView.extend({
    childView: AnnouncementEditableView,
    emptyView: AnnouncementListEmptyEditableView,
}) {
    initialize(options) {
        this.objectAttachedTo = options.objectAttachedTo;
    }

    childViewOptions(model) {
        return {
            objectAttachedTo: this.objectAttachedTo,
            collection: this.collection,
        };
    }
}

export default {
    AnnouncementEditableView: AnnouncementEditableView,
    AnnouncementMessageView: AnnouncementMessageView,
    AnnouncementEditableCollectionView: AnnouncementEditableCollectionView,
};
