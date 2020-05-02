/**
 *
 * @module app.views.loader
 */

import _ from "underscore";
import IdeaLoom from "../app.js";
import Ctx from "../common/context.js";
import { View } from "backbone.marionette";

class LoaderView extends View.extend({
    template: "#tmpl-loader",
}) {
    onRender() {
        // Get rid of that pesky wrapping-div.
        // Assumes 1 child element present in template.
        this.$el = this.$el.children();

        // Unwrap the element to prevent infinitely
        // nesting elements during re-render.
        this.$el.unwrap();
        this.setElement(this.$el);
    }
}

export default LoaderView;
