/**
 * @module app.views.preferencesView
 */

import { View, CollectionView } from "backbone.marionette";
import Backbone from "backbone";
import _ from "underscore";
import BackboneSubset from "Backbone.Subset";
import Promise from "bluebird";

import i18n from "../utils/i18n.js";
import Types from "../utils/types.js";
import Ctx from "../common/context.js";
import Permissions from "../utils/permissions.js";
import DiscussionPreference from "../models/discussionPreference.js";
import CollectionManager from "../common/collectionManager.js";
import AdminNavigationMenu from "./admin/adminNavigationMenu.js";
import UserNavigationMenu from "./user/userNavigationMenu.js";
import LoaderView from "./loaderView.js";
import Growl from "../utils/growl.js";

/**
 * @function app.views.preferencesView.getModelElementaryType
 * Get the type of the model at a given depth given by the subViewKey
 */
function getModelElementaryType(modelType, subViewKey, useKey) {
    if (subViewKey !== undefined) {
        subViewKey = String(subViewKey).split("_");
    }
    while (true) {
        var isList = modelType.substring(0, 8) == "list_of_";
        var isDict = modelType.substring(0, 8) == "dict_of_";
        if (isList) {
            if (subViewKey !== undefined && subViewKey.length > 0) {
                modelType = modelType.substring(8);
                subViewKey.shift();
            } else {
                return "list";
            }
        } else if (isDict) {
            if (subViewKey !== undefined) {
                var boundary = modelType.indexOf("_to_");
                if (
                    boundary === -1 ||
                    modelType.substring(8, boundary).indexOf("_") !== -1
                ) {
                    throw new Error("Invalid dict_of specification");
                }
                // only use the key on the last step
                if (useKey && subViewKey.length === 1) {
                    modelType = modelType.substring(8, boundary);
                    if (modelType.indexOf("_") !== -1) {
                        throw new Error("Invalid dict_of specification");
                    }
                } else {
                    modelType = modelType.substring(boundary + 4);
                }
                subViewKey.shift();
            } else {
                return "dict";
            }
        } else {
            break;
        }
    }

    if (modelType == "langstr") {
        // convenience function
        if (subViewKey !== undefined && subViewKey.length > 0) {
            if (useKey) {
                return "locale";
            } else {
                return "string";
            }
        } else {
            return "dict";
        }
    }
    return modelType;
}

/**
 * @function app.views.preferencesView.getPreferenceEditView
 * Get the appropriate subclass of BasePreferenceView
 */
function getPreferenceEditView(preferenceModel, subViewKey, useKey) {
    var modelType = getModelElementaryType(
        preferenceModel.value_type,
        subViewKey,
        useKey
    );

    switch (modelType) {
        case "list":
            return ListPreferenceView;
        case "dict":
            return DictPreferenceView;
        case "bool":
            return BoolPreferenceView;
        case "text":
            return TextPreferenceView;
        case "json":
            return JsonPreferenceView;
        case "int":
            return IntPreferenceView;
        case "permission":
            return PermissionPreferenceView;
        case "role":
            return RolePreferenceView;
        case "pubflow":
            return PubFlowPreferenceView;
        case "pubstate":
            return PubStatePreferenceView;
        case "string":
            return StringPreferenceView;
        case "password":
            return PasswordPreferenceView;
        case "scalar":
            return ScalarPreferenceView;
        case "locale":
            return LocalePreferenceView;
        case "url":
            return UrlPreferenceView;
        case "email":
            return EmailPreferenceView;
        case "domain":
            return DomainPreferenceView;
        default:
            console.error("Not edit view for preference of type " + modelType);
            return undefined;
    }
}

/**
 * A single preference item
 * @class app.views.preferencesView.PreferencesItemView
 */
class PreferencesItemView extends View.extend({
    regions: {
        subview: ".js_prefItemSubview",
    },

    ui: {
        resetButton: ".js_reset",
        errorMessage: ".control-error",
        controlGroup: ".control-group",
    },

    events: {
        "click @ui.resetButton": "resetPreference",
    },

    template: "#tmpl-preferenceItemView",
    isKeyView: false,
}) {
    resetPreference() {
        var that = this;
        var model = this.model;
        model.sync("delete", this.model, {
            success: function (model1, resp) {
                model.sync("read", model, {
                    success: function (model2, resp2) {
                        // this should be done by backbone, but isn't because we have a success?
                        model.set(that.key, model2);
                        // neutralize change
                        model.changed = {};
                        model._subcollectionCache = undefined;
                        Growl.showBottomGrowl(
                            Growl.GrowlReason.SUCCESS,
                            i18n.gettext("Your settings were reset to default")
                        );
                        that.render();
                    },
                    error: function (model, resp) {
                        Growl.showBottomGrowl(
                            Growl.GrowlReason.ERROR,
                            i18n.gettext(
                                "Your settings were not be reset, but could not be read back."
                            )
                        );
                        resp.handled = true;
                    },
                });
            },
            error: function (model, resp) {
                Growl.showBottomGrowl(
                    Growl.GrowlReason.ERROR,
                    i18n.gettext("Your settings could not be reset.")
                );
                resp.handled = true;
            },
        });
        return false;
    }

    initialize(options) {
        this.mainPrefWindow = options.mainPrefWindow;
        this.preferences = options.mainPrefWindow.preferences;
        this.key = options.key || this.model.id;
        this.listKey = options.listKey;
        this.preferenceData = options.mainPrefWindow.preferenceData[this.key];
        this.listCollectionView = options.listCollectionView;
        this.childViewOptions = {
            mainPrefWindow: options.mainPrefWindow,
            key: this.key,
            model: this.model,
            listKey: this.listKey,
            preferenceData: this.preferenceData,
            preferenceItemView: this,
            preference: this.model.get("value"),
        };
    }

    serializeData() {
        var model = this.model;
        if (this.listKey !== undefined) {
            var listKey = String(this.listKey).split("_");
            var lastKey = parseInt(listKey[listKey.length - 1]);
            model = this.listCollectionView.listView.submodels.models[lastKey];
        }
        return {
            i18n: i18n,
            preference: model.get(this.isKeyView ? "key" : "value"), // isKeyView of editview, really...
            preferenceData: this.preferenceData,
            canModify: this.mainPrefWindow.canSavePreference(this.key),
            listKey: this.listKey,
            inList: this.listKey !== undefined,
        };
    }

    onRender() {
        var subview = getPreferenceEditView(this.preferenceData, this.listKey);
        if (subview) {
            this.showChildView("subview", new subview(this.childViewOptions));
        } else {
            console.error(
                "Missing preference subview for ",
                this.preferenceData
            );
        }
    }

    showError(error) {
        this.ui.errorMessage.text(error);
        this.ui.errorMessage.removeClass("hidden");
        this.ui.controlGroup.addClass("error");
    }

    hideError(error) {
        this.ui.errorMessage.addClass("hidden");
        this.ui.errorMessage.text();
        this.ui.controlGroup.removeClass("error");
    }
}

/**
 * A single preference item in a ListPreferenceView
 * @class app.views.preferencesView.ListPreferencesItemView
 * @extends app.views.preferencesView.PreferencesItemView
 */
class ListPreferencesItemView extends PreferencesItemView.extend({
    ui: {
        deleteButton: ".js_delete",
        errorMessage: ".control-error",
        controlGroup: ".control-group",
    },

    events: {
        "click @ui.deleteButton": "deleteItem",
    },

    template: "#tmpl-listPreferenceItemView",
}) {
    deleteItem(event) {
        this.model.collection.remove(this.model);
        this.listCollectionView.render();
        return false;
    }
}

/**
 * Abstract class for preference views
 * @class app.views.preferencesView.BasePreferenceView
 */
class BasePreferenceView extends View.extend({
    ui: {
        prefValue: ".pref_value",
    },

    events: {
        "change @ui.prefValue": "prefChanged",
    },

    template: "#tmpl-basePreferenceView",
    tagName: "span",
}) {
    // isKeyView: false,
    valueModelKey() {
        return this.isKeyView ? "key" : "value";
    }

    initialize(options) {
        this.mainPrefWindow = options.mainPrefWindow;
        this.preferences = options.mainPrefWindow.preferences;
        this.key = options.key;
        this.preferenceData = options.mainPrefWindow.preferenceData[this.key];
        this.listKey = options.listKey;
        this.preferenceItemView = options.preferenceItemView;
        this.isKeyView = options.isKeyView;
    }

    prefChanged() {
        var value = this.getValue();
        try {
            value = this.processValue(value);
            this.preferenceItemView.hideError();
            this.model.set(this.valueModelKey(), value);
        } catch (err) {
            this.preferenceItemView.showError(err);
        }
    }

    getValue() {
        return this.ui.prefValue.val();
    }

    serializeData() {
        var preferenceValue = this.model.get(this.valueModelKey());
        return {
            i18n: i18n,
            preference: preferenceValue,
            preferenceData: this.preferenceData,
            canModify: this.mainPrefWindow.canSavePreference(this.key),
            inList: this.listKey !== undefined,
        };
    }

    processValue(value) {
        return value;
    }
}

/**
 * View to set a Boolean preference
 * @class app.views.preferencesView.BoolPreferenceView
 * @extends app.views.preferencesView.BasePreferenceView
 */
class BoolPreferenceView extends BasePreferenceView.extend({
    template: "#tmpl-boolPreferenceView",
}) {
    getValue() {
        return this.ui.prefValue.filter(":checked").val() !== undefined;
    }
}

/**
 * View to set a text preference
 * @class app.views.preferencesView.TextPreferenceView
 * @extends app.views.preferencesView.BasePreferenceView
 */
class TextPreferenceView extends BasePreferenceView.extend({
    template: "#tmpl-textPreferenceView",
}) {}

/**
 * View to set a JSON value preference
 * @class app.views.preferencesView.JsonPreferenceView
 * @extends app.views.preferencesView.TextPreferenceView
 */
class JsonPreferenceView extends TextPreferenceView.extend({
    template: "#tmpl-jsonPreferenceView",
}) {
    processValue(value) {
        try {
            return JSON.parse(value);
        } catch (err) {
            throw i18n.gettext("This is not valid JSON: ") + err.message;
        }
    }
}

/**
 * View to set a string value preference
 * @class app.views.preferencesView.StringPreferenceView
 * @extends app.views.preferencesView.BasePreferenceView
 */
class StringPreferenceView extends BasePreferenceView.extend({
    template: "#tmpl-stringPreferenceView",
}) {}

/**
 * View to set a hidden string value preference
 * @class app.views.preferencesView.PasswordPreferenceView
 * @extends app.views.preferencesView.BasePreferenceView
 */
class PasswordPreferenceView extends BasePreferenceView.extend({
    template: "#tmpl-passwordPreferenceView",
}) {}

/**
 * A single preference item in a DictPreferenceView
 * @class app.views.preferencesView.DictPreferencesItemView
 * @extends app.views.preferencesView.PreferencesItemView
 */
class DictPreferencesItemView extends PreferencesItemView.extend({
    ui: {
        deleteButton: ".js_delete",
        errorMessage: ".control-error",
        controlGroup: ".control-group",
    },

    regions: {
        key_subview: ".js_prefKeySubview",
        val_subview: ".js_prefValueSubview",
    },

    events: {
        "click @ui.deleteButton": "deleteItem",
    },

    template: "#tmpl-dictPreferenceItemView",
    keySubview: StringPreferenceView,
}) {
    deleteItem(event) {
        this.model.collection.remove(this.model);
        this.listCollectionView.render();
        return false;
    }

    onRender() {
        var key_subview = getPreferenceEditView(
            this.preferenceData,
            this.listKey,
            true
        );
        var val_subview = getPreferenceEditView(
            this.preferenceData,
            this.listKey
        );
        var key_options = _.clone(this.childViewOptions);
        _.extend(key_options, { isKeyView: true });
        this.showChildView("key_subview", new key_subview(key_options));
        if (val_subview) {
            this.showChildView(
                "val_subview",
                new val_subview(this.childViewOptions)
            );
        } else {
            console.error(
                "Missing preference subview for ",
                this.preferenceData
            );
        }
    }
}

/**
 * View to set an integer value preference
 * @class app.views.preferencesView.IntPreferenceView
 * @extends app.views.preferencesView.StringPreferenceView
 */
class IntPreferenceView extends StringPreferenceView {
    processValue(value) {
        try {
            return Number.parseInt(value);
        } catch (err) {
            throw i18n.gettext("Please enter a number");
        }
    }
}

/**
 * View to set a scalar value preference (chosen from a set)
 * @class app.views.preferencesView.ScalarPreferenceView
 * @extends app.views.preferencesView.BasePreferenceView
 */
class ScalarPreferenceView extends BasePreferenceView.extend({
    template: "#tmpl-scalarPreferenceView",
}) {
    serializeData() {
        var data = super.serializeData(...arguments);
        // Note: This is unsorted. Maybe should by value?
        data.scalarOptions = data.preferenceData.scalar_values;
        return data;
    }
}

/**
 * View to set a locale value preference (chosen from the set of locales)
 * @class app.views.preferencesView.LocalePreferenceView
 * @extends app.views.preferencesView.ScalarPreferenceView
 */
class LocalePreferenceView extends ScalarPreferenceView {
    serializeData() {
        var data = super.serializeData(...arguments);
        data.scalarOptions = Ctx.getLocaleToLanguageNameCache();
        return data;
    }
}

/**
 * View to set a permission value preference (chosen from the set of permissions)
 * @class app.views.preferencesView.PermissionPreferenceView
 * @extends app.views.preferencesView.ScalarPreferenceView
 */
class PermissionPreferenceView extends ScalarPreferenceView {
    serializeData() {
        var data = super.serializeData(...arguments);
        data.scalarOptions = {};
        _.each(Permissions, function (key) {
            data.scalarOptions[key] = key;
        });
        return data;
    }
}

/**
 * View to set a role value preference (chosen from the set of roles)
 * @class app.views.preferencesView.RolePreferenceView
 * @extends app.views.preferencesView.ScalarPreferenceView
 */
class RolePreferenceView extends ScalarPreferenceView {
    initialize(options) {
        super.initialize(...arguments);
        this.roles = Ctx.getRoleNames();
    }

    serializeData() {
        var data = super.serializeData(...arguments);
        data.scalarOptions = {};
        _.each(this.roles, function (key) {
            data.scalarOptions[key] = key;
        });
        return data;
    }
}

/**
 * View to set a role value preference (chosen from the set of roles)
 * @class app.views.preferencesView.PubFlowPreferenceView
 * @extends app.views.preferencesView.ScalarPreferenceView
 */
class PubFlowPreferenceView extends ScalarPreferenceView {
    constructor() {
        super(...arguments);
        this.pubFlowCollection = null;
    }

    initialize(options) {
        super.initialize(...arguments);
        const collectionManager = new CollectionManager();
        collectionManager
            .getAllPublicationFlowsPromise()
            .then((pubFlowCollection) => {
                this.pubFlowCollection = pubFlowCollection;
                this.render();
            });
    }

    serializeData() {
        var data = super.serializeData(...arguments);
        data.scalarOptions = {};
        if (this.pubFlowCollection) {
            this.pubFlowCollection.each((pubFlowModel) => {
                const label = pubFlowModel.get("label");
                data.scalarOptions[label] = label;
            });
        }
        return data;
    }
}

/**
 * View to set a role value preference (chosen from the set of roles)
 * @class app.views.preferencesView.PubFlowPreferenceView
 * @extends app.views.preferencesView.ScalarPreferenceView
 */
class PubStatePreferenceView extends ScalarPreferenceView {
    constructor() {
        super(...arguments);
        this.pubStateCollection = null;
        this.langPrefs = null;
    }

    initialize(options) {
        super.initialize(...arguments);
        const collectionManager = new CollectionManager();
        if (Ctx.getDiscussionId() != "0") {
            collectionManager
                .getIdeaPublicationStatesPromise()
                .then((pubStateCollection) => {
                    this.pubStateCollection = pubStateCollection;
                    this.render();
                });
            collectionManager
                .getUserLanguagePreferencesPromise(Ctx)
                .then((langPrefs) => {
                    this.langPrefs = langPrefs;
                    if (this.pubStateCollection) this.render();
                })
                .catch((e) => {
                    e.stopPropagation();
                    e.preventDefault();
                });
        } else {
            // TODO, not urgent: get the default publication states
        }
    }

    serializeData() {
        var data = super.serializeData(...arguments);
        data.scalarOptions = {};
        const langPrefs = this.langPrefs;
        if (this.pubStateCollection) {
            this.pubStateCollection.each((pubStateModel) => {
                const label = pubStateModel.get("label");
                const name = langPrefs
                    ? pubStateModel.nameOrLabel(langPrefs)
                    : label;
                data.scalarOptions[label] = name;
            });
        }
        return data;
    }
}

/**
 * View to set a URL value preference
 * @class app.views.preferencesView.UrlPreferenceView
 * @extends app.views.preferencesView.StringPreferenceView
 */
class UrlPreferenceView extends StringPreferenceView.extend({
    regexp: new RegExp(
        "^(?:(?:http|https|ftp)://)(?:\\S+(?::\\S*)?@)?(?:(?:(?:[1-9]\\d?|1\\d\\d|2[01]\\d|22[0-3])(?:\\.(?:1?\\d{1,2}|2[0-4]\\d|25[0-5])){2}(?:\\.(?:[0-9]\\d?|1\\d\\d|2[0-4]\\d|25[0-4]))|(?:(?:[a-z\\u00a1-\\uffff0-9]+-?)*[a-z\\u00a1-\\uffff0-9]+)(?:\\.(?:[a-z\\u00a1-\\uffff0-9]+-?)*[a-z\\u00a1-\\uffff0-9]+)*(?:\\.(?:[a-z\\u00a1-\\uffff]{2,})))|localhost)(?::\\d{2,5})?(?:(/|\\?|#)[^\\s]*)?$",
        "i"
    ),
}) {
    processValue(value) {
        if (!this.regexp.test(value)) {
            throw i18n.gettext("This does not appear to be a URL");
        }
        return value;
    }
}

/**
 * View to set an email value preference
 * @class app.views.preferencesView.EmailPreferenceView
 * @extends app.views.preferencesView.StringPreferenceView
 */
class EmailPreferenceView extends StringPreferenceView.extend({
    regexp: new RegExp("^[A-Z0-9._%+-]+@[A-Z0-9.-]+.[A-Z]{2,}$"),
}) {
    processValue(value) {
        if (!this.regexp.test(value)) {
            throw i18n.gettext("This does not appear to be an email");
        }
        return value;
    }
}

/**
 * View to set a domain (DNS name) value preference
 * @class app.views.preferencesView.DomainPreferenceView
 * @extends app.views.preferencesView.StringPreferenceView
 */
class DomainPreferenceView extends StringPreferenceView.extend({
    // too lenient: accepts single element ("com")
    regexp: new RegExp(
        "^[a-zA-Z0-9][a-zA-Z0-9-_]{0,61}[a-zA-Z0-9]{0,1}.([a-zA-Z]{1,6}|[a-zA-Z0-9-]{1,30}.[a-zA-Z]{2,3})$"
    ),
}) {
    processValue(value) {
        if (!this.regexp.test(value)) {
            throw i18n.gettext("This does not appear to be a domain");
        }
        return value.toLowerCase();
    }
}

/**
 * The collection view for the items in a preference-as-list
 * @class app.views.preferencesView.ListSubviewCollectionView
 */
class ListSubviewCollectionView extends CollectionView.extend({
    childView: ListPreferencesItemView,
}) {
    initialize(options) {
        this.mainPrefWindow = options.mainPrefWindow;
        this.preferences = options.preferences;
        this.key = options.key;
        this.listKey = options.listKey;
        this.listView = options.listView;
        this.preferenceData = options.preferenceData;
    }

    childViewOptions(model) {
        // This is bizarrely called before initialize;
        // then we have the options in the object
        var options = this.options;

        var index = this.collection.indexOf(model);
        if (options === undefined) {
            options = this;
        }
        if (this.listKey != undefined) {
            index = this.listKey + "_" + index;
        }
        return {
            mainPrefWindow: options.mainPrefWindow,
            listCollectionView: this,
            preferences: options.preferences,
            key: options.key,
            preferenceData: options.preferenceData,
            isList: true,
            // or model itself?
            // model: this.collection.models[index],
            listKey: index,
        };
    }
}

/**
 * The collection view for the items in a preference-as-dict
 * @class app.views.preferencesView.DictSubviewCollectionView
 */
class DictSubviewCollectionView extends CollectionView.extend({
    childView: DictPreferencesItemView,
}) {
    initialize(options) {
        this.mainPrefWindow = options.mainPrefWindow;
        this.preferences = options.preferences;
        this.key = options.key;
        this.listKey = options.listKey;
        this.listView = options.listView;
        this.preferenceData = options.preferenceData;
    }

    childViewOptions(model) {
        // This is bizarrely called before initialize;
        // then we have the options in the object
        var options = this.options;

        var index = this.collection.indexOf(model);
        if (options === undefined) {
            options = this;
        }
        if (this.listKey != undefined) {
            index = this.listKey + "_" + index;
        }
        return {
            mainPrefWindow: options.mainPrefWindow,
            listCollectionView: this,
            preferences: options.preferences,
            key: options.key,
            preferenceData: options.preferenceData,
            isList: true,
            // model: this.collection.models[index],
            listKey: index,
        };
    }
}

/**
 * A single preference which is a list
 * @class app.views.preferencesView.ListPreferenceView
 * @extends app.views.preferencesView.BasePreferenceView
 */
class ListPreferenceView extends BasePreferenceView.extend({
    ui: {
        addToList: ".js_add_to_listpref",
    },

    regions: {
        listPreference: ".js_listPreference",
    },

    events: {
        "click @ui.addToList": "addToList",
    },

    template: "#tmpl-listPreferenceView",
    subviewClass: ListSubviewCollectionView,
}) {
    initialize(options, is_dict) {
        super.initialize(options);
        this.submodels = this.model.valueAsCollection(
            this.preferenceData,
            is_dict
        );
    }

    onRender() {
        var subview = new this.subviewClass({
            collection: this.submodels,
            mainPrefWindow: this.mainPrefWindow,
            preferences: this.preferences,
            key: this.key,
            listView: this,
            listKey: this.listKey,
            preferenceData: this.preferenceData,
        });
        this.showChildView("listPreference", subview);
    }

    extractDefaultVal(defaultVal, listKey) {
        var i = 0;
        if (listKey !== undefined) {
            i = String(listKey).split("_").length;
        }
        for (; i > 0; i--) {
            if (_.isArray(defaultVal)) {
                defaultVal = defaultVal[0];
            } else {
                // only use one
                _.each(defaultVal, function (val) {
                    defaultVal = val;
                });
                // special case: dict of list, go down another level.
                if (
                    _.isArray(defaultVal) &&
                    getModelElementaryType(
                        this.preferenceData.value_type,
                        this.listKey,
                        false
                    ) == "list"
                ) {
                    defaultVal = defaultVal[0];
                }
            }
        }
        if (_.isObject(defaultVal)) {
            // shallow clone, hopefully good enough
            defaultVal = _.clone(defaultVal);
        }
        return defaultVal;
    }

    asModel(val) {
        return new DiscussionPreference.Model({ value: val }, { parse: false });
    }

    addToList() {
        var defaultVal = this.extractDefaultVal(
            this.preferenceData.item_default,
            this.listKey
        );
        var model = this.asModel(defaultVal);
        this.submodels.add([model]);
        this.render();
        return false;
    }
}

/**
 * A single preference which is a dict
 * @class app.views.preferencesView.DictPreferenceView
 * @extends app.views.preferencesView.ListPreferenceView
 */
class DictPreferenceView extends ListPreferenceView.extend({
    subviewClass: DictSubviewCollectionView,
}) {
    initialize(options) {
        super.initialize(options, true);
        this.submodels = this.model.valueAsCollection(
            this.preferenceData,
            false
        );
    }

    asModel(value) {
        var key;
        var val;
        // only use one
        _.each(value, function (v, k) {
            key = k;
            val = v;
        });
        return new DiscussionPreference.Model(
            { key: key, value: val },
            { parse: false }
        );
    }
}

/**
 * The list of all preferences
 * @class app.views.preferencesView.PreferencesCollectionView
 */
class PreferencesCollectionView extends CollectionView.extend({
    childView: PreferencesItemView,
}) {
    initialize(options) {
        this.mainPrefWindow = options.mainPrefWindow;
        this.childViewOptions = {
            mainPrefWindow: options.mainPrefWindow,
        };
    }
}

/**
 * Which preferences will we show?
 * @class app.views.preferencesView.PreferenceCollectionSubset
 */
class PreferenceCollectionSubset extends Backbone.Subset {
    beforeInitialize(models, options) {
        var preferenceData = options.parent.get("preference_data");
        var modifiable = _.filter(
            preferenceData.get("value"),
            this.prefDataSieve
        );
        var keys = {};
        _.map(modifiable, function (pd) {
            keys[pd.id] = true;
        });
        this.keys = keys;
    }

    prefDataSieve(pd) {
        return true;
    }

    sieve(preference) {
        return this.keys[preference.id];
    }
}

/**
 * The subset of preferences which allow a per-user override
 * @class app.views.preferencesView.UserPreferenceCollectionSubset
 * @extends app.views.preferencesView.PreferenceCollectionSubset
 */
class UserPreferenceCollectionSubset extends PreferenceCollectionSubset {
    prefDataSieve(pd) {
        return (
            pd.allow_user_override !== undefined &&
            Ctx.getCurrentUser().can(pd.allow_user_override)
        );
    }
}

/**
 * The subset of preferences which allow a per-discussion override
 * @class app.views.preferencesView.DiscussionPreferenceCollectionSubset
 * @extends app.views.preferencesView.PreferenceCollectionSubset
 */
class DiscussionPreferenceCollectionSubset extends PreferenceCollectionSubset {
    prefDataSieve(pd) {
        return pd.show_in_preferences !== false;
    }
}

/**
 * The subset of preferences which allow a per-discussion override
 * @class app.views.preferencesView.GlobalPreferenceCollectionSubset
 * @extends app.views.preferencesView.PreferenceCollectionSubset
 */
class GlobalPreferenceCollectionSubset extends PreferenceCollectionSubset {
    prefDataSieve(pd) {
        // TODO
        return true;
    }
}

/**
 * The preferences window
 * @class app.views.preferencesView.PreferencesView
 */
class PreferencesView extends LoaderView.extend({
    template: "#tmpl-preferenceView",

    ui: {
        saveButton: "#js_savePreferences",
    },

    events: {
        "click @ui.saveButton": "save",
    },

    regions: {
        preferenceCollView: "#js_preferences",
        navigationMenuHolder: ".navigation-menu-holder",
    },
}) {
    initialize() {
        this.setLoading(true);
    }

    onRender() {
        if (this.isLoading()) {
            return;
        }
        var prefList = new PreferencesCollectionView({
            collection: this.preferences,
            mainPrefWindow: this,
        });
        this.showChildView("preferenceCollView", prefList);
        this.showChildView("navigationMenuHolder", this.getNavigationMenu());
    }

    storePreferences(prefs) {
        var prefDataArray = prefs.get("preference_data").get("value");
        var prefData = {};
        _.map(prefDataArray, function (pref) {
            prefData[pref.id] = pref;
        });
        this.allPreferences = prefs;
        this.preferenceData = prefData;
        this.setLoading(false);
        this.render();
    }

    save() {
        var that = this;
        var errors = [];
        var complete = 0;

        var toSave = this.allPreferences.filter(function (model) {
            return model.hasChanged();
        });

        function do_complete() {
            complete += 1;
            if (complete == toSave.length) {
                if (errors.length > 0) {
                    var names = _.map(errors, function (id) {
                        return that.preferenceData[id].name;
                    });
                    Growl.showBottomGrowl(
                        Growl.GrowlReason.ERROR,
                        i18n.gettext(
                            "The following settings were not saved: "
                        ) + names.join(", ")
                    );
                } else {
                    Growl.showBottomGrowl(
                        Growl.GrowlReason.SUCCESS,
                        i18n.gettext("Your settings were saved!")
                    );
                }
            }
        }
        if (toSave.length == 0) {
            Growl.showBottomGrowl(
                Growl.GrowlReason.SUCCESS,
                i18n.gettext("Your settings are up-to-date.")
            );
        } else {
            _.map(toSave, function (model) {
                model.save(null, {
                    success: function (model) {
                        do_complete();
                    },
                    error: function (model, resp) {
                        errors.push(model.id);
                        do_complete();
                        resp.handled = true;
                    },
                });
            });
        }
        return false;
    }
}

/**
 * The discussion preferences window
 * @class app.views.preferencesView.DiscussionPreferencesView
 * @extends app.views.preferencesView.PreferencesView
 */
class DiscussionPreferencesView extends PreferencesView {
    initialize() {
        this.setLoading(true);
        var that = this;
        var collectionManager = new CollectionManager();
        collectionManager
            .getDiscussionPreferencePromise()
            .then(function (prefs) {
                that.preferences = new DiscussionPreferenceCollectionSubset(
                    [],
                    { parent: prefs }
                );
                that.storePreferences(prefs);
            });
    }

    canSavePreference(id) {
        var prefData = this.preferenceData[id];
        var neededPerm =
            prefData.modification_permission || Permissions.ADMIN_DISCUSSION;
        return Ctx.getCurrentUser().can(neededPerm);
    }

    getNavigationMenu() {
        return new AdminNavigationMenu.discussionAdminNavigationMenu({
            selectedSection: "discussion_preferences",
        });
    }
}

/**
 * The preferences window for global (instance-level) preferences
 * @class app.views.preferencesView.GlobalPreferencesView
 * @extends app.views.preferencesView.PreferencesView
 */
class GlobalPreferencesView extends PreferencesView {
    constructor() {
        super(...arguments);
        this.setLoading(true);
    }

    initialize() {
        var that = this;
        var collectionManager = new CollectionManager();
        collectionManager.getGlobalPreferencePromise().then(function (prefs) {
            that.preferences = new GlobalPreferenceCollectionSubset([], {
                parent: prefs,
            });
            that.storePreferences(prefs);
        });
    }

    canSavePreference(id) {
        return Ctx.getCurrentUser().can(Permissions.SYSADMIN);
    }

    getNavigationMenu() {
        return new AdminNavigationMenu.globalAdminNavigationMenu({
            selectedSection: "global_preferences",
        });
    }
}

/**
 * The user preferences window
 * @class app.views.preferencesView.UserPreferencesView
 * @extends app.views.preferencesView.PreferencesView
 */
class UserPreferencesView extends PreferencesView {
    initialize() {
        this.setLoading(true);
        var that = this;
        var collectionManager = new CollectionManager();
        collectionManager.getUserPreferencePromise().then(function (prefs) {
            that.preferences = new UserPreferenceCollectionSubset([], {
                parent: prefs,
            });
            that.storePreferences(prefs);
        });
    }

    canSavePreference(id) {
        var prefData = this.preferenceData[id];
        var neededPerm = prefData.allow_user_override;
        if (neededPerm === undefined) {
            // vs null
            neededPerm = Permissions.P_READ;
        }
        return Ctx.getCurrentUser().can(neededPerm);
    }

    getNavigationMenu() {
        return new UserNavigationMenu({
            selectedSection: "discussion_preferences",
        });
    }
}

export default {
    DiscussionPreferencesView: DiscussionPreferencesView,
    GlobalPreferencesView: GlobalPreferencesView,
    UserPreferencesView: UserPreferencesView,
};
