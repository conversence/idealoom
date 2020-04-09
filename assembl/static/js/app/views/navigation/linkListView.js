/**
 *
 * @module app.views.navigation.linkListView
 */

import _ from "underscore";

import $ from "jquery";
import Promise from "bluebird";
import Marionette from "backbone.marionette";
import Ctx from "../../common/context.js";
import Permissions from "../../utils/permissions.js";

class SimpleLinkView extends Marionette.View.extend({
    template: "#tmpl-simpleLink",

    ui: {
        links: ".externalvizlink",
    },

    events: {
        "click @ui.links": "linkClicked",
    },
}) {
    initialize(options) {
        this.groupContent = options.groupContent;
    }

    linkClicked(a) {
        var content = this.groupContent;
        Ctx.deanonymizationCifInUrl(this.model.get("url"), function (url) {
            content.NavigationResetVisualizationState(url);
        });
    }
}

class LinkListView extends Marionette.CollectionView.extend({
    childView: SimpleLinkView,
}) {
    initialize(options) {
        this.collection = options.collection;
        this.groupContent = options.groupContent;
        this.childViewOptions = {
            groupContent: options.groupContent,
        };
    }
}

export default LinkListView;
