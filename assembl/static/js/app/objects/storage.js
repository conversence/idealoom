/**
 *
 * @module app.objects.storage
 */

import Marionette from "backbone.marionette";

import groupSpec from "../models/groupSpec.js";
import Ctx from "../common/context.js";

class storage extends Marionette.Object.extend({
    _store: window.localStorage,
}) {
    getStoragePrefix() {
        var interfaceType = Ctx.getCurrentInterfaceType();
        var storagePrefix;
        if (interfaceType === Ctx.InterfaceTypes.SIMPLE) {
            storagePrefix = "simpleInterface";
        } else if (interfaceType === Ctx.InterfaceTypes.EXPERT) {
            storagePrefix = "expertInterface";
        } else {
            console.log(
                "storage::initialize unknown interface type: ",
                interfaceType
            );
        }

        return storagePrefix;
    }

    bindGroupSpecs(groupSpecs) {
        var that = this;
        this.groupSpecs = groupSpecs;
        this.listenTo(groupSpecs, "add", this.addGroupSpec);
        this.listenTo(groupSpecs, "remove", this.removeGroupSpec);
        this.listenTo(groupSpecs, "reset change", this.saveGroupSpecs);
        groupSpecs.models.forEach(function (m) {
            that.listenTo(
                m.attributes.panels,
                "add remove reset change",
                that.saveGroupSpecs
            );
            that.listenTo(
                m.attributes.states,
                "add remove reset change",
                that.saveGroupSpecs
            );
        });
    }

    addGroupSpec(groupSpec, groupSpecs) {
        this.listenTo(
            groupSpec.attributes.panels,
            "add remove reset change",
            this.saveGroupSpecs
        );
        this.saveGroupSpecs();
    }

    removeGroupSpec(groupSpec, groupSpecs) {
        this.stopListening(groupSpec);
        this.saveGroupSpecs();
    }

    saveGroupSpecs() {
        //console.log("saveGroupSpecs:", JSON.stringify(this.groupSpecs));
        this._store.setItem(
            this.getStoragePrefix() + "groupItems",
            JSON.stringify(this.groupSpecs)
        );
        this._store.setItem(
            this.getStoragePrefix() + "lastViewSave",
            Date.now()
        );
    }

    getDateOfLastViewSave() {
        var lastSave = this._store.getItem(
            this.getStoragePrefix() + "lastViewSave"
        );
        if (lastSave) {
            return new Date(parseInt(lastSave));
        }
    }

    getStorageGroupItem() {
        if (this._store.getItem(this.getStoragePrefix() + "groupItems")) {
            return JSON.parse(
                this._store.getItem(this.getStoragePrefix() + "groupItems")
            );
        }
    }
}

export default new storage();
