/**
 *
 * @module app.views.flipSwitchButton
 */

import { View } from "backbone.marionette";

class FlipSwitchButton extends View.extend({
    template: "#tmpl-flipSwitchButton",
    className: "flipSwitchButton",

    ui: {
        toggleButton: ".js_toggleButton",
    },

    events: {
        "click @ui.toggleButton": "onToggle",
    },

    modelEvents: {
        "change:isOn": "updateState", // this is the same as writing this.listenTo(this.model, 'change:isOn', this.updateState); in the initialize() method
    },
}) {
    // the serializeData() method is not needed because model attributes are sent automatically to the template

    onToggle() {
        this.model.set("isOn", !this.model.get("isOn"));

        //this.updateState(); // will be done automatically thanks to modelEvents
    }

    // does a smooth re-render (so that CSS animations are shown)
    updateState() {
        console.log("flipSwitchButton::updateState()");
        if (this.model.get("isOn")) {
            this.ui.toggleButton.removeClass("flipswitch-no");
            this.ui.toggleButton.addClass("flipswitch-yes");
        } else {
            this.ui.toggleButton.removeClass("flipswitch-yes");
            this.ui.toggleButton.addClass("flipswitch-no");
        }
    }
}

export default FlipSwitchButton;
