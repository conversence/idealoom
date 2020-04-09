/**
 * Represents an independent group of panels in the interface. When added, the matching views (groupContainerView) will be instanciated
 * @module app.models.groupSpec
 */
import Base from "./base.js";

import panelSpec from "./panelSpec.js";
import PanelSpecTypes from "../utils/panelSpecTypes.js";
import groupState from "./groupState.js";

/**
 * Group specifications model
 * @class app.models.groupSpec.GroupSpecModel
 * @extends app.models.base.BaseModel
 */
class GroupSpecModel extends Base.Model {
    /**
     * Set panelSpec and groupState in model attributes
     * @returns {Object}
     * @function app.models.groupSpec.GroupSpecModel.defaults
     */
    defaults() {
        return {
            panels: new panelSpec.Collection(),
            states: new groupState.Collection([new groupState.Model()]),
        };
    }

    /**
     * @param {Object} model
     * @returns {Object}
     * @function app.models.groupSpec.GroupSpecModel.parse
     */
    parse(model) {
        model.panels = new panelSpec.Collection(model.panels, { parse: true });
        if (model.states && model.states.length > 0) {
            model.states = new groupState.Collection(model.states, {
                parse: true,
            });
        } else {
            model.states = this.defaults().states;
        }
        return model;
    }

    /**
     * Remove panel specs from model
     * @function app.models.groupSpec.GroupSpecModel.removePanels
     */
    removePanels() {
        var args = Array.prototype.slice.call(arguments);
        var panels = this.get("panels");
        var panelsToRemove = _.filter(panels.models, function (el) {
            return _.contains(args, el.getPanelSpecType());
        });
        _.each(panelsToRemove, function (el) {
            panels.remove(el);
        });
    }

    /**
     * Remove panel specs from model
     * @param {aPanelSpec} aPanelSpec
     * @function app.models.groupSpec.GroupSpecModel.removePanelByModel
     */
    removePanelByModel(aPanelSpec) {
        this.get("panels").remove(aPanelSpec);
    }

    /**
     * Returns the part of the groupSpec that contains the navigation panel (if any).
     * That is, any panel in the first position that has the capacity to alter the global group state
     * @returns {Object}
     * @function app.models.groupSpec.GroupSpecModel.findNavigationPanelSpec
     */
    findNavigationPanelSpec() {
        var navigationTypes = PanelSpecTypes.getNavigationPanelTypes();
        var panelAtFirstPositionTypeId = this.get("panels").at(0).get("type");

        var panelSpecType = _.find(navigationTypes, function (navigationType) {
            return navigationType.id === panelAtFirstPositionTypeId;
        });

        return panelSpecType;
    }

    /**
     * Returns the part of the groupSpec that contains the simple interface navigation panel (if any)
     * @returns {Object}
     * @function app.models.groupSpec.GroupSpecModel.findNavigationSidebarPanelSpec
     */
    findNavigationSidebarPanelSpec() {
        return this.get("panels").findWhere({
            type: PanelSpecTypes.NAV_SIDEBAR.id,
        });
    }

    /**
     * Add panel specs to model
     * @param {Object} options
     * @param {Int} position
     * @function app.models.groupSpec.GroupSpecModel.addPanel
     */
    addPanel(options, position) {
        var aPanelSpec = new panelSpec.Model(options);
        if (!aPanelSpec.isValid()) {
            throw new Error(
                "Can't add an invalid panelSpec, error was: " +
                    aPanelSpec.validationError
            );
        }
        var panels = this.get("panels");
        if (position === undefined) {
            panels.add(aPanelSpec);
        } else {
            panels.add(aPanelSpec, { at: position });
        }
    }

    /**
     * Returns panel sepcs by type
     * @param {Object} panelSpecType
     * @function app.models.groupSpec.GroupSpecModel.getPanelSpecByType
     */
    getPanelSpecByType(panelSpecType) {
        var validPanelSpecType = PanelSpecTypes.validate(panelSpecType);
        if (validPanelSpecType === undefined) {
            throw new Error("invalid panelSpecType");
        }
        return _.find(this.get("panels").models, function (el) {
            return el.getPanelSpecType() === validPanelSpecType;
        });
    }

    /**
     * Find or create panels at a given position
     * Note that despite the name, this function does NOT check that if the panel exists, it exists at the right position.
     * It ONLY check that the panel exists
     * @param {Array} list_of_options - PanelType or array of PanelType
     * @param {Int} position - int order of first panel listed in sequence of panels
     * @function app.models.groupSpec.GroupSpecModel.ensurePanelsAt
     */
    ensurePanelsAt(list_of_options, position) {
        var that = this;
        if (!Array.isArray(list_of_options)) {
            list_of_options = [list_of_options];
        }
        if (
            _.any(list_of_options, function (el) {
                return !PanelSpecTypes.validate(el);
            })
        ) {
            throw new Error(
                "One of the panelSpecTypes in the option isn't valid"
            );
        }
        var that = this;
        _.each(list_of_options, function (option) {
            if (!that.getPanelSpecByType(option)) {
                that.addPanel({ type: option.id }, position);
            }
            position++;
        });
    }

    /**
     * Validate the model attributes
     * @function app.models.groupSpec.GroupSpecModel.validate
     */
    validate() {
        var navstate = this.get("navigationState");
        //Migrate old data
        if (navstate == "home") {
            this.set("navigationState", "about");
        }
        // check other values for validity?
        var panels = this.get("panels");
        return panels.validate();
    }
}

/**
 * Group specifications collection
 * @class app.models.groupSpec.GroupSpecs
 * @extends app.models.base.BaseCollection
 */
class GroupSpecs extends Base.Collection.extend({
    /**
     * The model
     * @type {GroupSpecModel}
     */
    model: GroupSpecModel,
}) {
    /**
     * Validate the model attributes
     * @function app.models.groupSpec.GroupSpecs.validate
     */
    validate() {
        var invalid = [];
        this.each(function (groupSpec) {
            if (!groupSpec.validate()) {
                invalid.push(groupSpec);
            }
        });
        if (invalid.length) {
            console.log(
                "GroupSpec.Collection: removing " +
                    invalid.length +
                    " invalid groupSpecs from " +
                    this.length +
                    " groupSpecs."
            );
            this.remove(invalid);
            console.log(
                "GroupSpec.Collection: after removal, number of remaining valid groupSpecs: ",
                this.length
            );
        }
        return this.length > 0;
    }
}

export default {
    Model: GroupSpecModel,
    Collection: GroupSpecs,
};
