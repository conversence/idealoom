/**
 *
 * @module app.views.reusableDataFields.EditableLSField
 */

import _ from "underscore";
import $ from "jquery";
import IdeaLoom from "../../app.js";
import Permissions from "../../utils/permissions.js";
import LangString from "../../models/langstring.js";
import CK from "ckeditor";
import EditableField from "./editableField.js";
import Ctx from "../../common/context.js";

class EditableLSField extends EditableField {
    /**
     * CkLSeditor default configuration
     * @type {object}
     */

    initialize(options) {
        if (this.model === null) {
            throw new Error("EditableField needs a model");
        }
        if (this.translationData === null) {
            // Or just current Ctx.getLocale()?
            throw new Error("EditableField needs translationData");
        }
        this.translationData = options.translationData;
        super.initialize(...arguments);
    }

    getTextValue() {
        var ls = this.model.get(this.modelProp);
        if (!ls) {
            return "";
        }
        if (this.editing) {
            // use interface value for edition
            return ls.forInterfaceValue() || "";
        }
        return ls.bestValue(this.translationData);
    }

    setTextValue(text) {
        var lse;
        var attrs = {};
        var ls = this.model.get(this.modelProp);
        if (!ls) {
            ls = new LangString.Model();
            ls.initFromDict({});
        }
        lse = ls.forInterface();
        if (!lse) {
            lse = new LangString.EntryModel({
                value: text,
                "@language": Ctx.getLocale(),
            });
            ls.get("entries").add(lse);
        } else {
            lse.set("value", text);
            lse.set("@language", Ctx.getLocale()); // i.e. clear translation status
            lse.set("error_code", undefined);
        }
        attrs[this.modelProp] = ls;
        this.model.save(attrs, {
            success: function (model, resp) {},
            error: function (model, resp) {
                console.error("ERROR: saveEdition", resp.responseJSON);
            },
        });
    }
}

export default EditableLSField;
