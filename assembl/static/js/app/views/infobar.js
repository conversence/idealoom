/**
 *
 * @module app.views.infobar
 */

import Backbone from "backbone";

import BackboneModal from "backbone.modal";
import { View, CollectionView } from "backbone.marionette";
import IdeaLoom from "../app.js";
import CookiesManager from "../utils/cookiesManager.js";
import Widget from "../models/widget.js";
import InfobarsCollection from "../models/infobar.js";
import Ctx from "../common/context.js";
import LoaderView from "./loaderView.js";
import CollectionManager from "../common/collectionManager.js";
import $ from "jquery";
import i18n from "../utils/i18n.js";

class CookieInfobarItemView extends View.extend({
    template: "#tmpl-cookieBanner",

    ui: {
        acceptCookiesBtn: "#js_accept-cookie-btn",
        refuseCookiesBtn: "#js_refuse-cookie-btn",
    },

    events: {
        "click @ui.refuseCookiesBtn": "openCookiesSettings",
        "click @ui.acceptCookiesBtn": "closeInfobar",
    },
}) {
    openCookiesSettings() {
        var piwikIframe = new PiwikIframeModal();
        IdeaLoom.rootView.showChildView("slider", piwikIframe);
        this.closeInfobar();
    }

    closeInfobar() {
        CookiesManager.setUserCookiesAuthorization();
        this.destroy();
        this.model.set("closeInfobar", true);
        IdeaLoom.other_vent.trigger("infobar:closeItem");
    }
}

class TosInfobarItemView extends View.extend({
    template: "#tmpl-tos_infobar",

    events: {
        "click .js_closeInfobar": "closeInfobar",
    },
}) {
    serializeModel() {
        var model = this.model.get("widget");
        return {
            model: model,
            message: i18n.sprintf(
                i18n.gettext(
                    'Please review our new <a href="/%s/user/tos">Terms of service</a>'
                ),
                Ctx.getDiscussionSlug()
            ),
            locale: Ctx.getLocale(),
        };
    }

    closeInfobar() {
        this.destroy();
        this.model.set("closeInfobar", true);
        IdeaLoom.other_vent.trigger("infobar:closeItem");
    }
}

class PiwikIframeModal extends Backbone.Modal.extend({
    template: "#tmpl-piwikIframeModal",
    className: "modal-ckeditorfield popin-wrapper",
    keyControl: false,
    cancelEl: ".close",
}) {
    getStatsUrl() {
        // var url = "//piwik.coeus.ca/index.php?module=CoreAdminHome&action=optOut&language=fr";
        var url = analyticsUrl;
        if (!(url[url.length - 1] === "/")) {
            url = url + "/";
        }
        url = url + "index.php?module=CoreAdminHome&action=optOut&language=";
        var locale = Ctx.getLocale() || "fr"; // Either get the locale, or the default is French
        url = url + locale;
        // console.log("URL of statistics on Inforbar.js", url);
        return url;
    }

    serializeData() {
        return {
            statsUrl: this.getStatsUrl(),
        };
    }
}

class WidgetInfobarItemView extends LoaderView.extend({
    template: "#tmpl-widget_infobar",
    className: "content-infobar",

    ui: {
        button: ".btn",
    },

    events: {
        "click @ui.button": "onButtonClick",
        "click .js_closeInfobar": "closeInfobar",
        "click .js_openSession": "openSession",
        "click .js_openTargetInModal": "openTargetInModal",
    },
}) {
    initialize() {
        var that = this;
        var collectionManager = new CollectionManager();
        this.setLoading(true);
        collectionManager
            .getUserLanguagePreferencesPromise(Ctx)
            .then(function (ulp) {
                that.translationData = ulp;
                that.setLoading(false);
                that.render();
            });
    }

    onButtonClick(evt) {
        if (evt && _.isFunction(evt.preventDefault)) {
            evt.preventDefault();
        }
        var context = Widget.Model.prototype.INFO_BAR;
        var model = this.model.get("widget");
        var openTargetInModalOnButtonClick =
            model.getCssClasses(context).indexOf("js_openTargetInModal") != -1;
        if (openTargetInModalOnButtonClick !== false) {
            var options = {
                footer: false,
            };
            Ctx.openTargetInModal(evt, null, options);
        } else {
            this.model.trigger("buttonClick", context);
        }
        return false;
    }

    serializeModel() {
        var model = this.model.get("widget");
        return {
            model: model,
            message: model.getDescriptionText(
                Widget.Model.prototype.INFO_BAR,
                undefined,
                this.translationData
            ),
            call_to_action_msg: model.getLinkText(
                Widget.Model.prototype.INFO_BAR
            ),
            share_link: model.getShareUrl(Widget.Model.prototype.INFO_BAR),
            widget_endpoint: model.getUrl(Widget.Model.prototype.INFO_BAR),
            call_to_action_class: model.getCssClasses(
                Widget.Model.prototype.INFO_BAR
            ),
            locale: Ctx.getLocale(),
            shows_button: model.showsButton(Widget.Model.prototype.INFO_BAR),
        };
    }

    closeInfobar() {
        this.destroy();
        this.model.set("closeInfobar", true);
        IdeaLoom.other_vent.trigger("infobar:closeItem");
    }
}

class InfobarsView extends CollectionView.extend({
    collectionEvents: {
        "add remove reset change": "adjustInfobarSize",
    },
}) {
    childView(item) {
        switch (item.view_name) {
            case InfobarsCollection.prototype.view_names.WIDGET:
                return WidgetInfobarItemView;
            case InfobarsCollection.prototype.view_names.COOKIE:
                return CookieInfobarItemView;
            case InfobarsCollection.prototype.view_names.TOS:
                return TosInfobarItemView;
            default:
                console.error("Unknown item view_name", item.view_name);
        }
    }

    initialize(options) {
        this.childViewOptions = {
            parentPanel: this,
        };
        this.adjustInfobarSize();
    }

    //TO DO: refactor because should not be necessary to set the top of 'groupContainer' in js file
    adjustInfobarSize(evt) {
        var el = IdeaLoom.rootView.getRegion("groupContainer").$el;
        var n = this.collection.length;
        this.collection.each(function (itemView) {
            if (itemView.get("closeInfobar")) {
                n--;
            }
        });
        for (var i = n - 2; i <= n + 2; i++) {
            if (i === n) {
                el.addClass("hasInfobar-" + String(i));
            } else {
                el.removeClass("hasInfobar-" + String(i));
            }
        }
    }
}

export default {
    InfobarsView: InfobarsView,
};
