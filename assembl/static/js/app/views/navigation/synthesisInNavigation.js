/**
 *
 * @module app.views.navigation.synthesisInNavigation
 */

import { CollectionView } from "backbone.marionette";

import _ from "underscore";
import $ from "jquery";
import Promise from "bluebird";
import BasePanel from "../basePanel.js";
import CollectionManager from "../../common/collectionManager.js";
import Types from "../../utils/types.js";
import IdeaLoom from "../../app.js";
import Ctx from "../../common/context.js";
import i18n from "../../utils/i18n.js";
import PanelSpecTypes from "../../utils/panelSpecTypes.js";
import scrollUtils from "../../utils/scrollUtils.js";
import LoaderView from "../loaderView.js";
import Analytics from "../../internal_modules/analytics/dispatcher.js";

class SynthesisItem extends LoaderView.extend({
    template: "#tmpl-synthesisItemInNavigation",

    events: {
        "click .js_synthesisList": "onSelectedSynthesis",
    },
}) {
    initialize(options) {
        var that = this;
        this.setLoading(true);
        this.panel = options.panel;
        this.model.collection.collectionManager
            .getUserLanguagePreferencesPromise(Ctx)
            .then(function (ulp) {
                that.translationData = ulp.getTranslationData();
                that.setLoading(false);
                that.render();
            });
    }

    serializeData() {
        if (this.isLoading()) {
            return {};
        }
        return {
            id: this.model.get("published_in_post"),
            subject: this.model.get("subject").bestValue(this.translationData),
            date: Ctx.formatDate(this.model.get("created")),
        };
    }

    onSelectedSynthesis(e) {
        var messageId = $(e.currentTarget).attr("data-message-id");
        this.panel.displaySynthesis(messageId);
        //If it's a small screen detected => scroll to the right
        if (Ctx.isSmallScreen()) {
            var screenSize = window.innerWidth;
            scrollUtils.scrollToNextPanel(".groupsContainer", 100, screenSize);
        }
    }
}

class SynthesisList extends CollectionView.extend({
    childView: SynthesisItem,
}) {
    initialize(options) {
        var publishedSyntheses = this.collection.getPublishedSyntheses();

        _.sortBy(publishedSyntheses, function (message) {
            return message.get("created");
        });
        publishedSyntheses.reverse();

        this.collection = new Backbone.Collection(publishedSyntheses);

        this.childViewOptions = {
            panel: options.panel,
        };
    }
}

class SynthesisInNavigationPanel extends BasePanel.extend({
    template: "#tmpl-synthesisInNavigationPanel",
    panelType: PanelSpecTypes.NAVIGATION_PANEL_SYNTHESIS_SECTION,
    className: "synthesisNavPanel",

    ui: {
        synthesisListHeader: ".synthesisListHeader",
    },

    regions: {
        synthesisContainer: ".synthesisList",
    },
}) {
    initialize(options) {
        super.initialize(...arguments);
        var that = this;
        var collectionManager = new CollectionManager();
        this.setLoading(true);

        Promise.join(
            collectionManager.getAllMessageStructureCollectionPromise(),
            collectionManager.getAllSynthesisCollectionPromise(),
            function (allMessageStructureCollection, allSynthesisCollection) {
                if (!that.isDestroyed()) {
                    that.setLoading(false);
                    that.allMessageStructureCollection = allMessageStructureCollection;
                    that.allSynthesisCollection = allSynthesisCollection;
                    that.render();
                }
            }
        );
    }

    selectSynthesisInMenu(messageId) {
        $(".synthesisItem").closest("li").removeClass("selected");
        this.$('.synthesisItem[data-message-id="' + messageId + '"]').addClass(
            "selected"
        );
    }

    displaySynthesis(messageId) {
        var analytics = Analytics.getInstance();

        analytics.trackEvent(
            analytics.events.NAVIGATION_OPEN_SPECIFIC_SYNTHESIS
        );
        var messageListView = this.getContainingGroup().findViewByType(
            PanelSpecTypes.MESSAGE_LIST
        );
        messageListView.currentQuery.clearAllFilters();
        messageListView.toggleFilterByPostId(messageId);
        messageListView.showMessageById(messageId, undefined, false);

        setTimeout(function () {
            if (messageListView.ui.stickyBar) {
                messageListView.ui.stickyBar.addClass("hidden");
            }
            if (messageListView.ui.replyBox) {
                messageListView.ui.replyBox.addClass("hidden");
            }
        }, 1);

        // Show that entry is selected
        this.selectSynthesisInMenu(messageId);
    }

    displaySynthesisList(
        allMessageStructureCollection,
        allSynthesisCollection
    ) {
        var lastPublisedSynthesis = allSynthesisCollection.getLastPublisedSynthesis();

        if (lastPublisedSynthesis) {
            var synthesisList = new SynthesisList({
                collection: allSynthesisCollection,
                panel: this,
            });

            this.showChildView("synthesisContainer", synthesisList);
            this.displaySynthesis(
                lastPublisedSynthesis.get("published_in_post")
            );
        } else {
            this.ui.synthesisListHeader.html(
                i18n.gettext(
                    "No synthesis of the discussion has been published yet"
                )
            );
        }
    }

    onRender() {
        var that = this;
        var collectionManager = new CollectionManager();

        if (!this.isLoading() && !this.isDestroyed()) {
            this.displaySynthesisList(
                this.allMessageStructureCollection,
                this.allSynthesisCollection
            );
            this.listenTo(
                this.allSynthesisCollection,
                "add reset",
                function () {
                    //console.log("Re-displaying synthesis list from collection update...", allSynthesisCollection.length);
                    that.displaySynthesisList(
                        that.allMessageStructureCollection,
                        that.allSynthesisCollection
                    );
                }
            );
            // that.getRegion('synthesisContainer').$el.find(".synthesisItem:first")[0].id = "tour_step_synthesis_item1";
            // IdeaLoom.tour_vent.trigger("requestTour", "synthesis_item1");
        }
    }
}

export default SynthesisInNavigationPanel;
