/**
 *
 * @module app.views.navigation.about
 */

import IdeaLoom from "../../app.js";

import BasePanel from "../basePanel.js";
import PanelSpecTypes from "../../utils/panelSpecTypes.js";
import Analytics from "../../internal_modules/analytics/dispatcher.js";

class AboutNavPanel extends BasePanel.extend({
    template: "#tmpl-about",
    panelType: PanelSpecTypes.NAVIGATION_PANEL_ABOUT_SECTION,
    className: "aboutNavPanel",

    ui: {
        debate: ".js_go-to-debate",
    },

    events: {
        "click @ui.debate": "goToDebate",
        "click .js_test_stuff_analytics": "testAnalytics",
        "click .js_trackInteractionExample": "testAnalytics2",
    },
}) {
    goToDebate() {
        IdeaLoom.other_vent.trigger("DEPRECATEDnavigation:selected", "debate");
    }

    testAnalytics(e) {
        e.stopPropagation();
        e.preventDefault();
        var a = Analytics.getInstance();
        a.trackImpression(
            "DummyContentName",
            "DummyContentPiece",
            "http://dummyurl.fc.uk"
        );
    }

    testAnalytics2(e) {
        e.stopPropagation();
        e.preventDefault();
        var a = Analytics.getInstance();
        a.trackContentInteraction(
            "DummyInteraction",
            "DummyContentName",
            "DummyContentPiece",
            "http://dummyurl.fc.uk"
        );
    }
}

export default AboutNavPanel;
