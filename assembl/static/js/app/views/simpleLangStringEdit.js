/**
 * A simple editor for langstring models, mostly for back-office use
 * @module app.views.admin.simpleLangStringEdit
 */

import IdeaLoom from "../app.js";

import Ctx from "../common/context.js";
import i18n from "../utils/i18n.js";
import EditableField from "./reusableDataFields/editableField.js";
import LangString from "../models/langstring.js";
import CollectionManager from "../common/collectionManager.js";
import Marionette from "backbone.marionette";
import Growl from "../utils/growl.js";
import $ from "jquery";
import _ from "underscore";
import Promise from "bluebird";

/**
 * @class  app.views.admin.simp.SimpleLangStringEditPanel
 */
class SimpleLangStringEditPanel extends Marionette.View.extend({
    template: "#tmpl-simpleLangStringEdit",

    ui: {
        addEntry: ".js_add_entry",
        entryList: ".js_entryList",
    },

    regions: {
        entryList: "@ui.entryList",
    },

    events: {
        "click @ui.addEntry": "addEntry",
    },
}) {
    initialize(options) {
        if (this.isDestroyed()) {
            return;
        }
        this.langCache = Ctx.localesAsSortedList();
        this.model = options.model;
        this.owner_relative_url = options.owner_relative_url;
    }

    addEntry(ev) {
        var langstring = this.model;
        var entries = langstring.get("entries");
        var entry = new LangString.EntryModel();
        entries.add(entry);
        // saving will happen after entry has changed value
        ev.preventDefault();
    }

    onRender() {
        if (this.isDestroyed()) {
            return;
        }
        this.showChildView(
            "entryList",
            new LangStringEntryList({
                basePanel: this,
                langstring: this.model,
                owner_relative_url: this.owner_relative_url,
                collection: this.model.get("entries"),
            })
        );
    }
}

/**
 * @class  app.views.admin.adminMessageColumns.LangStringEntryView
 */
class LangStringEntryView extends Marionette.View.extend({
    template: "#tmpl-langStringEntry",

    ui: {
        locale: ".js_locale",
        value: ".js_value",
        deleteButton: ".js_delete",
    },

    events: {
        "change @ui.locale": "changeLocale",
        "change @ui.value": "changeValue",
        "click @ui.deleteButton": "deleteEntry",
    },
}) {
    initialize(options) {
        this.languages = options.basePanel.langCache;
        this.owner_relative_url = options.owner_relative_url;
    }

    serializeData() {
        return {
            languages: this.languages,
            model: this.model,
        };
    }

    modelUrl() {
        var url =
            this.owner_relative_url +
            "/" +
            this.model.langstring().getNumericId() +
            "/entries";
        if (this.model.id !== undefined) {
            url += "/" + this.model.getNumericId();
        }
        return url;
    }

    deleteEntry(ev) {
        this.model.destroy({ url: this.modelUrl() });
        ev.preventDefault();
    }

    changeLocale(ev) {
        var that = this;
        this.model.save(
            {
                "@language": ev.currentTarget.value,
            },
            {
                url: this.modelUrl(),
            }
        );
        ev.preventDefault();
    }

    changeValue(ev) {
        var that = this;
        this.model.save(
            {
                value: ev.currentTarget.value,
            },
            {
                url: this.modelUrl(),
            }
        );
        ev.preventDefault();
    }
}

/**
 * The collections of columns to be seen on this idea
 * @class app.views.adminMessageColumns.LangStringEntryList
 */
class LangStringEntryList extends Marionette.CollectionView.extend({
    childView: LangStringEntryView,
}) {
    initialize(options) {
        this.childViewOptions = options;
    }
}

export default SimpleLangStringEditPanel;
