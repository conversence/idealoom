/**
 *
 * @module app.views.reusableDataFields.trueFalseField
 */

import _ from "underscore";
import IdeaLoom from "../../app.js";
import Ctx from "../../common/context.js";
import { View } from "backbone.marionette";

class TrueFalseField extends View.extend({
    template: "#tmpl-trueFalseField",

    attributes: {
        class: "TrueFalseField",
    },

    events: {
        change: "onChange",
    },
}) {
    initialize(options) {
        this.view = this;

        this.canEdit = _.has(options, "canEdit") ? options.canEdit : true;
        this.modelProp = _.has(options, "modelProp") ? options.modelProp : null;

        if (this.model === null) {
            throw new Error("TrueFalseField needs a model");
        }
        if (this.modelProp === null) {
            throw new Error("TrueFalseField needs a modelProp");
        }
        if (this.model.get(this.modelProp) === undefined) {
            throw new Error(
                this.modelProp + " must be initialised to true or false"
            );
        }
    }

    onRender() {
        this.$("input:checkbox").prop(
            "checked",
            this.model.get(this.modelProp)
        );
        this.$("input:checkbox").prop("disabled", !this.canEdit);
    }

    onChange(ev) {
        if (this.canEdit) {
            var data = this.$("input:checkbox").prop("checked");
            if (this.model.get(this.modelProp) != data) {
                /* Nor save to the database and fire change events
                 * if the value didn't change from the model
                 */
                this.model.save(this.modelProp, data, {
                    success: function (model, resp) {},
                    error: function (model, resp) {
                        console.error("ERROR: onChange", resp);
                    },
                });
            }
        }
    }
}

export default TrueFalseField;
