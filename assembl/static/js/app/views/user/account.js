/**
 *
 * @module app.views.user.account
 */

import Marionette from "backbone.marionette";

import $ from "jquery";
import _ from "underscore";
import Accounts from "../../models/accounts.js";
import Ctx from "../../common/context.js";
import Agents from "../../models/agents.js";
import UserNavigationMenu from "./userNavigationMenu.js";
import i18n from "../../utils/i18n.js";
import Growl from "../../utils/growl.js";

class email extends Marionette.View.extend({
    template: "#tmpl-associateAccount",
    className: "associate-email mbs",

    ui: {
        verifyEmail: ".js_verifyEmail",
    },

    events: {
        "click @ui.verifyEmail": "verifyEmail",
    },
}) {
    serializeData() {
        return {
            email: this.model,
        };
    }

    verifyEmail() {
        var urlRoot =
            this.model.urlRoot +
            "/" +
            this.model.get("@id").split("/")[1] +
            "/verify";

        var verify = new Backbone.Model();
        verify.url = urlRoot;

        verify.save(null, {
            success: function (model, resp) {
                console.log("success", resp);
            },
            error: function (model, resp) {
                console.log("error", resp);
            },
        });
    }
}

class emailListBody extends Marionette.CollectionView.extend({
    childView: email,
}) {}

class emailList extends Marionette.View.extend({
    template: "#tmpl-associateAccounts",

    regions: {
        body: ".controls",
    },
}) {
    onRender() {
        this.showChildView(
            "body",
            new emailListBody({
                collection: this.collection,
            })
        );
    }
}

class socialProvidersList extends Marionette.View.extend({
    template: "#tmpl-socialProviders",
}) {
    initialize(options) {
        this.providers = options.providers;
    }

    serializeData() {
        return { i18n: i18n, providers: this.providers };
    }
}

class userAccount extends Marionette.View.extend({
    template: "#tmpl-userAccountForm",

    ui: {
        account: ".js_saveAccount",
    },

    events: {
        "click @ui.account": "saveAccount",
    },

    modelEvents: {
        "add change": "render",
    },
}) {
    serializeData() {
        return {
            user: this.model,
        };
    }

    saveAccount(e) {
        e.preventDefault();

        var pass1 = this.$('input[name="new_password"]');
        var pass2 = this.$('input[name="confirm_password"]');
        var user = this.$('input[name="username"]');
        var p_pass1 = pass1.parent().parent();
        var p_pass2 = pass2.parent().parent();

        if (pass1.val() || pass2.val()) {
            if (pass1.val() !== pass2.val()) {
                p_pass1.addClass("error");
                p_pass2.addClass("error");
                return false;
            } else if (pass1.val() === pass2.val()) {
                p_pass1.addClass("error");
                p_pass2.addClass("error");

                this.model.set({
                    username: user.val(),
                    password: pass1.val(),
                });
            }
        } else {
            this.model.set({ username: user.val() });
        }

        this.model.save(null, {
            success: function (model, resp) {
                Growl.showBottomGrowl(
                    Growl.GrowlReason.SUCCESS,
                    i18n.gettext("Your settings were saved!")
                );
            },
            error: function (model, resp) {
                Growl.showBottomGrowl(
                    Growl.GrowlReason.ERROR,
                    i18n.gettext("Your settings failed to update.")
                );
            },
        });
    }
}

class account extends Marionette.View.extend({
    template: "#tmpl-userAccount",
    className: "admin-account",

    regions: {
        navigationMenuHolder: ".navigation-menu-holder",
        accounts: "#associate_accounts",
        social_accounts: "#associate_social_accounts",
        accountForm: "#userAccountForm",
    },

    ui: {
        addEmail: ".js_addEmail",
    },

    events: {
        "click @ui.addEmail": "addEmail",
    },
}) {
    initialize() {
        this.emailCollection = new Accounts.Collection();
        this.userAcount = new Agents.Model({ "@id": Ctx.getCurrentUserId() });
        this.userAcount.fetch();
        this.providers = Ctx.getJsonFromScriptTag("login-providers");
    }

    onRender() {
        var menu = new UserNavigationMenu({ selectedSection: "account" });
        this.showChildView("navigationMenuHolder", menu);
        var email_domain_constraints = Ctx.getPreferences()
            .require_email_domain;
        if (email_domain_constraints.length == 0) {
            var accounts = new emailList({
                collection: this.emailCollection,
            });
            this.emailCollection.fetch();
            this.showChildView("accounts", accounts);

            var providers = new socialProvidersList({
                providers: this.providers,
            });

            // disable until I complete the work
            this.showChildView("social_accounts", providers);
        }

        var userAccountForm = new userAccount({
            model: this.userAcount,
        });
        this.showChildView("accountForm", userAccountForm);
    }

    addEmail(e) {
        e.preventDefault();

        var that = this;
        var email = this.$('input[name="new_email"]').val().trim();
        var emailRegex = /^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;

        if (!email) {
            Growl.showBottomGrowl(
                Growl.GrowlReason.ERROR,
                i18n.gettext("Empty email")
            );
            return;
        }

        if (!emailRegex.test(email)) {
            Growl.showBottomGrowl(
                Growl.GrowlReason.ERROR,
                i18n.gettext("Invalid email")
            );
            return;
        }

        var emailModel = new Accounts.Model({
            email: email,
            "@type": "EmailAccount",
        });

        emailModel.save(null, {
            success: function () {
                that.emailCollection.fetch();
                Growl.showBottomGrowl(
                    Growl.GrowlReason.SUCCESS,
                    i18n.gettext("Your settings were saved")
                );
            },
            error: function (model, resp) {
                resp.handled = true;
                var message = Ctx.getErrorMessageFromAjaxError(resp);
                if (message === null) {
                    message = i18n.gettext("Your settings failed to update");
                }
                Growl.showBottomGrowl(Growl.GrowlReason.ERROR, message);
            },
        });
    }
}

export default account;
