/**
 *
 * @module app.views.admin.adminDiscussionSettings
 */

import Marionette from "backbone.marionette";

import i18n from "../../utils/i18n.js";
import CollectionManager from "../../common/collectionManager.js";
import Sources from "../../models/sources.js";
import SourceView from "./generalSource.js";
import AdminNavigationMenu from "./adminNavigationMenu.js";

class AdminImportSettings extends Marionette.View.extend({
    template: "#tmpl-adminImportSettings",
    className: "admin-import",

    ui: {
        addSource: ".js_addSource",
    },

    events: {
        "click @ui.addSource": "addFakeFacebookSource",
    },

    regions: {
        sources: "#sources-content",
        createSource: "#create-source",
        navigationMenuHolder: ".navigation-menu-holder",
    },
}) {
    onRender() {
        var that = this;
        var collectionManager = new CollectionManager();

        collectionManager
            .getDiscussionSourceCollectionPromise2()
            .then(function (discussionSource) {
                that.collection = discussionSource;
                var discussionSourceList = new SourceView.DiscussionSourceList({
                    collection: discussionSource,
                });
                that.showChildView("sources", discussionSourceList);
            });

        this.showChildView("createSource", new SourceView.CreateSource());

        var menu = new AdminNavigationMenu.discussionAdminNavigationMenu({
            selectedSection: "import",
        });
        this.showChildView("navigationMenuHolder", menu);
    }

    addFakeFacebookSource(evt) {
        evt.preventDefault();

        //Mock facebook view
        // this.collection.add(new Sources.Model.Facebook({
        //   '@type': 'FacebookSinglePostSource',

        //   name: 'Benoit!'
        // }));
    }
}

export default AdminImportSettings;
