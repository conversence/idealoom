/**
 *
 * @module app.views.admin.adminDiscussion
 */

import Marionette from "backbone.marionette";

import $ from "jquery";
import _ from "underscore";
import autosize from "jquery-autosize";
import CollectionManager from "../../common/collectionManager.js";
import Ctx from "../../common/context.js";
import Growl from "../../utils/growl.js";
import Discussion from "../../models/discussion.js";
import DiscussionSource from "../../models/discussionSource.js";
import i18n from "../../utils/i18n.js";
import AdminNavigationMenu from "./adminNavigationMenu.js";

class adminDiscussion extends Marionette.View.extend({
    template: "#tmpl-adminDiscussion",
    className: "admin-discussion",

    ui: {
        discussion: ".js_saveDiscussion",
        logo: "#logo_url",
        logo_thumbnail: "#logo_thumbnail",
    },

    regions: {
        navigationMenuHolder: ".navigation-menu-holder",
    },

    events: {
        "click @ui.discussion": "saveDiscussion",
        "blur @ui.logo": "renderLogoThumbnail",
    },
}) {
    initialize() {
        var that = this;
        var collectionManager = new CollectionManager();

        this.model = undefined;

        collectionManager
            .getDiscussionModelPromise()
            .then(function (Discussion) {
                that.model = Discussion;
                that.render();
            });
    }

    onRender() {
        // this is in onRender instead of onBeforeShow because of the re-render in initialize()
        var menu = new AdminNavigationMenu.discussionAdminNavigationMenu({
            selectedSection: "edition",
        });
        this.showChildView("navigationMenuHolder", menu);

        this.$("#introduction").autosize();
        this.renderLogoThumbnail();
    }

    serializeData() {
        return {
            discussion: this.model,
            Ctx: Ctx,
        };
    }

    saveDiscussion(e) {
        e.preventDefault();

        var introduction = this.$("textarea[name=introduction]").val();
        var topic = this.$("input[name=topic]").val();
        var slug = this.$("input[name=slug]").val();
        var objectives = this.$("textarea[name=objectives]").val();
        var web_analytics_piwik_id_site = parseInt(
            this.$("#web_analytics_piwik_id_site").val()
        );
        var help_url = this.$("#help_url").val();
        var homepage_url = this.$("#homepage_url").val();
        var logo_url = this.ui.logo.val();
        var show_help_in_debate_section =
            this.$("#show_help_in_debate_section:checked").length == 1;

        this.model.set({
            introduction: introduction,
            topic: topic,
            slug: slug,
            objectives: objectives,
            web_analytics_piwik_id_site: web_analytics_piwik_id_site,
            help_url: help_url,
            logo: logo_url,
            homepage: homepage_url,
            show_help_in_debate_section: show_help_in_debate_section,
        });

        this.model.save(null, {
            success: function (model, resp, options) {
                Growl.showBottomGrowl(
                    Growl.GrowlReason.SUCCESS,
                    i18n.gettext("Your settings were saved!")
                );
            },
            error: function (model, resp, options) {
                Growl.showBottomGrowl(
                    Growl.GrowlReason.ERROR,
                    i18n.gettext("Your settings failed to update.")
                );
                resp.handled = true; //In order to avoid IdeaLoom crashing completely!
            },
        });
    }

    renderLogoThumbnail() {
        console.log("renderLogoThumbnail()");
        this.ui.logo_thumbnail.empty();
        var logo_url = this.ui.logo ? this.ui.logo.val() : null;
        console.log("logo_url: ", logo_url);
        if (logo_url) {
            var img = $("<img>");
            img.attr("src", this.ui.logo.val());
            //img.css("max-width", "115px");
            img.css("max-height", "40px");

            var thumbnail_description = i18n.gettext(
                "The logo will show like this:"
            );
            var text_el = $("<span>");
            text_el.addClass("mrl");
            text_el.text(thumbnail_description);
            this.ui.logo_thumbnail.append(text_el);
            this.ui.logo_thumbnail.append(img);
        }
    }
}

export default adminDiscussion;
