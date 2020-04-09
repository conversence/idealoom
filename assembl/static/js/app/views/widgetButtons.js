/**
 *
 * @module app.views.widgetButtons
 */

import Backbone from "backbone";

import Marionette from "backbone.marionette";
import _ from "underscore";
import i18n from "../utils/i18n.js";
import Moment from "moment";
import Widget from "../models/widget.js";
import Ctx from "../common/context.js";
import Permissions from "../utils/permissions.js";

class WidgetButtonView extends Marionette.View.extend({
    template: "#tmpl-widgetButton",

    ui: {
        button: ".btn",
    },

    events: {
        // "click @ui.button": "onButtonClick",
        "click .js_widget-vote": "onButtonClick",
        "click .js_widget-vote-result": "onResultButtonClick",
    },
}) {
    initialize(options) {
        this.options = options;
    }

    onButtonClick(evt) {
        console.log("WidgetButtonView::onButtonClick()");
        var context = this.options.context;
        var idea = this.options.idea;

        var openTargetInModalOnButtonClick =
            this.model
                .getCssClasses(context, idea)
                .indexOf("js_openTargetInModal") != -1;
        console.log(
            "openTargetInModalOnButtonClick: ",
            openTargetInModalOnButtonClick
        );
        if (openTargetInModalOnButtonClick !== false) {
            var options = {
                footer: false,
            };
            return Ctx.openTargetInModal(evt, null, options);
        } else {
            //Pass the event in case need to stop the default action of evt.
            this.model.trigger("buttonClick", evt);
        }
        return false;
    }

    onResultButtonClick(ev) {
        console.log("triggering 'showResult' event on model", this.model);
        this.model.trigger("showResult", ev);
    }

    serializeData() {
        var endDate = this.model.get("end_date");

        return {
            link: this.model.getUrl(
                this.options.context,
                this.options.idea.getId()
            ),
            button_text: this.model.getLinkText(
                this.options.context,
                this.options.idea
            ),
            description: this.model.getDescriptionText(
                this.options.context,
                this.options.idea,
                this.options.translationData
            ),
            classes: this.model.getCssClasses(
                this.options.context,
                this.options.idea
            ),
            until_text: this.model.getDescriptionText(
                this.model.UNTIL_TEXT,
                this.options.idea,
                this.options.translationData
            ),
            canSeeResults: Ctx.getCurrentUser().can(
                Permissions.ADMIN_DISCUSSION
            ),
        };
    }
}

class WidgetButtonListView extends Marionette.CollectionView.extend({
    childView: WidgetButtonView,
}) {
    initialize(options) {
        this.childViewOptions = {
            context: options.context || options.collection.context,
            idea: options.idea || options.collection.idea,
            translationData: options.translationData,
        };
        if (this.childViewOptions.context === undefined) {
            console.error("Undefined context in WidgetButtonListView");
        }
    }
}

export default {
    WidgetButtonView: WidgetButtonView,
    WidgetButtonListView: WidgetButtonListView,
};
