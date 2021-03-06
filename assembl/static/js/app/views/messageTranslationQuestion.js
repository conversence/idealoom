/**
 *
 * @module app.views.messageTranslationQuestion
 */
import Backbone from "backbone";
import Ctx from "../common/context.js";
import CollectionManager from "../common/collectionManager.js";
import i18n from "../utils/i18n.js";
import _ from "underscore";
import $ from "jquery";
import Types from "../utils/types.js";
import Growl from "../utils/growl.js";
import LangString from "../models/langstring.js";
import LoaderView from "./loaderView.js";
import LanguagePreference from "../models/languagePreference.js";
import { View } from "backbone.marionette";

/**
 * Date: Jan 14, 2016
 * Assumption: Currently, we are NOT showing the translation view if the SUBJECT of a message and only
 * the subject of the message is translated. Rather 'gung ho', but this is the reality.
 */

var userTranslationStates = {
    CONFIRM: "confirm",
    DENY: "deny",
    CANCEL: "cancel",
};

/*
    Callback function upon successfully setting a language preference;
    Used in both Views in this file.
 */
var processConfirmLanguagePreferences = function (messageView) {
    var cm = new CollectionManager();

    //Remove silent, remove messageListView.render()
    if (!messageView.isDestroyed()) {
        messageView.closeTranslationView(function () {
            cm.getAllMessageStructureCollectionPromise()
                .then(function (messageStructures) {
                    return messageStructures.fetch();
                })
                .then(function (messages) {
                    //Do not need to do anything else. The re-fetching of messages will cause the
                    //messagelist to re-render itself.
                    if (!messageView.isDestroyed()) {
                        messageView.resetTranslationState();
                        messageView.render(); // This is questionable.
                    }
                });
        });
    }
};

class LanguageSelectionView extends View.extend({
    template: "#tmpl-message_translation_question_selection",

    ui: {
        selectedLanguage: ".js_translate-to-language",
        confirm: ".js_translation-confirm",
        cancel: ".js_translation-cancel",
    },

    events: {
        "click @ui.confirm": "onConfirmClick",
        "click @ui.cancel": "onCancelClick",
    },
}) {
    initialize(options) {
        (this.parentView = options.questionView),
            (this.messageView = this.parentView.messageView);
        this.languagePreferences = this.parentView.languagePreferences;
        this.translatedTo = this.parentView.translatedTo;
        this.translatedFrom = this.parentView.translatedFrom;
        this.originalLocale = this.parentView.originalLocale;
        this.langCache = this.parentView.langCache;
    }

    nameOfLocale(locale) {
        var name = this.langCache[locale];
        if (name === undefined) {
            console.error(
                "The language " + locale + " is not a part of the locale cache!"
            );
            return locale;
        }
        return name;
    }

    onConfirmClick(e) {
        var that = this; //Will return Array
        var user = Ctx.getCurrentUser();
        var preferredLanguageTo = $(this.ui.selectedLanguage).val();

        if (!preferredLanguageTo) {
            Growl.showBottomGrowl(
                Growl.GrowlReason.ERROR,
                i18n.gettext("Please select a language.")
            );
            return;
        } else if (preferredLanguageTo.length > 1) {
            Growl.showBottomGrowl(
                Growl.GrowlReason.ERROR,
                i18n.gettext("You cannot select more than one language")
            );
            return;
        } else {
            this.parentView.preferredTarget = preferredLanguageTo[0];
            this.parentView.updateLanguagePreference(
                userTranslationStates.CONFIRM
            );
        }
    }

    onCancelClick(ev) {
        this.parentView.onLanguageSelectedCancelClick();
    }

    serializeData() {
        return {
            supportedLanguages: Ctx.localesAsSortedList(),
            translatedTo: this.translatedTo,
            question: i18n.sprintf(
                i18n.gettext(
                    "Select the language you wish to translate %s to:"
                ),
                this.nameOfLocale(
                    LangString.LocaleUtils.stripCountry(this.translatedFrom)
                )
            ),
            translatedFrom: this.translatedFrom,
        };
    }
}

class TranslationView extends LoaderView.extend({
    template: "#tmpl-message_translation_question",

    ui: {
        langChoiceConfirm: ".js_language-of-choice-confirm",
        langChoiceDeny: ".js_language-of-choice-deny",
        hideQuestion: ".js_hide-translation-question",

        revealLanguages: ".js_language-of-choice-more",
        // revealLanguagesRegion: '.js_translation-reveal-more'
    },

    events: {
        "click @ui.langChoiceConfirm": "updateLanguagePreferenceConfirm",
        "click @ui.langChoiceDeny": "updateLanguagePreferenceDeny",
        "click @ui.hideQuestion": "onHideQuestionClick",

        "click @ui.revealLanguages": "onLanguageRevealClick",
    },

    regions: {
        selectLanguage: ".js_translation-reveal-more",
    },
}) {
    initialize(options) {
        this.setLoading(true);
        this.message = options.messageModel;
        this.messageView = options.messageView;

        //Toggle flag for more languages view (nice to have)
        this.moreLanguagesViewShown = false;

        var cm = new CollectionManager();
        var that = this;

        cm.getUserLanguagePreferencesPromise(Ctx).then(function (preferences) {
            if (!that.isDestroyed()) {
                var translationData =
                    that.messageView.translationData ||
                    preferences.getTranslationData();
                that.langCache = that.messageView.langCache; //For reference
                var body = that.message.get("body") || LangString.Model.empty;
                var bestSuggestedTranslation = body.best(translationData);
                var original = body.original();
                var originalLocale = original.getLocaleValue();
                var translatedFromLocale = bestSuggestedTranslation.getTranslatedFromLocale();
                var translatedTo = bestSuggestedTranslation.getBaseLocale();
                var prefsForLocale = translationData.getPreferenceForLocale(
                    originalLocale
                );
                var preferredTarget = prefsForLocale
                    ? prefsForLocale.get("translate_to_name")
                    : Ctx.getLocale();
                if (!translatedFromLocale) {
                    translatedFromLocale = translatedTo;
                }
                that.originalLocale = originalLocale;
                that.translatedTo = translatedTo;
                that.translatedFrom = translatedFromLocale;
                that.preferredTarget = preferredTarget;
                that.languagePreferences = preferences; //Should be sorted already
                that.setLoading(false);
                that.render();
            }
        });
    }

    nameOfLocale(locale) {
        var name = this.langCache[locale];
        if (name === undefined) {
            console.error(
                "The language " + locale + " is not a part of the locale cache!"
            );
            return locale;
        }
        return name;
    }

    updateLanguagePreference(state) {
        var user = Ctx.getCurrentUser();
        var that = this;
        if (state === userTranslationStates.CONFIRM) {
            this.languagePreferences.setPreference(
                user,
                this.originalLocale,
                this.preferredTarget,
                {
                    success: function (model, resp, options) {
                        return processConfirmLanguagePreferences(
                            that.messageView
                        );
                    },
                }
            );
        }

        if (state === userTranslationStates.DENY) {
            this.languagePreferences.setPreference(
                user,
                this.originalLocale,
                null,
                {
                    success: function (model, resp, options) {
                        return processConfirmLanguagePreferences(
                            that.messageView
                        );
                    },
                }
            );
        }
    }

    updateLanguagePreferenceConfirm(e) {
        this.updateLanguagePreference(userTranslationStates.CONFIRM);
    }

    updateLanguagePreferenceDeny(e) {
        this.updateLanguagePreference(userTranslationStates.DENY);
    }

    onLanguageRevealClick(ev) {
        if (!this.moreLanguagesViewShown) {
            this.showChildView(
                "selectLanguage",
                new LanguageSelectionView({
                    messageModel: this.message,
                    questionView: this,
                })
            );
            this.moreLanguagesViewShown = true;
        } else {
            this.onLanguageSelectedCancelClick();
        }
    }

    /*
        Called by child class to destroy itself
        Since parent has to be passed through to child view,
        fuck using events to trigger this. Child explicitly calls this.
     */
    onLanguageSelectedCancelClick() {
        this.getRegion("selectLanguage").empty();
        this.moreLanguagesViewShown = false;
    }

    /*
        Hides the translation view into another element of the message
        Currently, that is the "Show More" dropdown
     */
    onHideQuestionClick(e) {
        var that = this;
        this.messageView.closeTranslationView(function () {
            console.log("The message is hidden by now");
        });
    }

    serializeData() {
        if (!this.isLoading()) {
            var translationQuestion;
            var noAnswer;
            var yesAnswer;
            var toAnother;
            if (this.preferredTarget) {
                translationQuestion = i18n.sprintf(
                    i18n.gettext("Translate all messages from %s to %s?"),
                    this.nameOfLocale(
                        LangString.LocaleUtils.stripCountry(this.originalLocale)
                    ),
                    this.nameOfLocale(
                        LangString.LocaleUtils.stripCountry(
                            this.preferredTarget
                        )
                    )
                );
                // yesAnswer = i18n.sprintf(
                //     i18n.gettext("Yes, translate all messages to %s"),
                //     this.nameOfLocale(this.preferredTarget));
                // noAnswer = i18n.sprintf(
                //     i18n.gettext("No, do not translate all messages to %s"),
                //     this.nameOfLocale(this.preferredTarget));
            } else {
                translationQuestion = i18n.sprintf(
                    i18n.gettext("Keep %s messages untranslated?"),
                    this.nameOfLocale(
                        LangString.LocaleUtils.stripCountry(this.originalLocale)
                    )
                );
                // noAnswer = i18n.sprintf(
                //     i18n.gettext("Yes, keep them untranslated"));
            }
            yesAnswer = i18n.gettext("Yes, Thanks!");
            noAnswer = i18n.gettext("Do not translate");
            toAnother = i18n.gettext("Translate to another language");

            return {
                translationQuestion: translationQuestion,
                yes: yesAnswer,
                no: noAnswer,
                toAnother: toAnother,
                preferredTarget: this.preferredTarget,
                originalLocale: this.originalLocale,
                translatedFromLocale: this.translatedFrom,
                translatedTo: this.translatedTo,
                forceTranslationQuestion: this.messageView
                    .forceTranslationQuestion,
            };
        }
    }
}

export default TranslationView;
