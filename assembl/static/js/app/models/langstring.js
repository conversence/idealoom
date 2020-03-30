/**
 * Manage string translation
 * @module app.models.langstring
 */
import _ from 'underscore';

import Base from './base.js';
import Ctx from '../common/context.js';
import i18n from '../utils/i18n.js';
import Types from '../utils/types.js';
/**
 * @class app.models.langstring.LocaleUtils
 */
var LocaleUtils = {
  translatorInfo: Ctx.getTranslationServiceData() || {},
  /**
   * @function app.models.langstring.LocaleUtils.localeCompatibility
   */
  localeCompatibility: function(locale1, locale2) {
    // Are the two locales similar enough to be substituted
    // one for the other. Mostly same language/script, disregard country.
    // shortcut
    if (locale1.substr(0, 2) != locale2.substr(0, 2)) {
      return false;
    }
    // Google special case
    if (locale1 == "zh")
        locale1 = "zh_Hans";
    if (locale2 == "zh")
        locale2 = "zh_Hans";
    var l1 = locale1.split("-x-mtfrom-")[0].split("_");
    var l2 = locale2.split("-x-mtfrom-")[0].split("_");
    var max = Math.min(l1.length, l2.length);
    for (var i = 0; i < max; i++) {
      if (l1[i] != l2[i]) {
        if (i > 0 && l1[i].length == 2) {
            return i;
        }
        return false;
      }
    }
    return i + 1;
  },

  undefined: "und",
  non_linguistic: "zxx",
  /**
   * @function app.models.langstring.LocaleUtils.stripCountry
   */
  stripCountry: function(locale) {
      var locale_parts = locale.split("_");
      if (locale_parts.length > 1 && locale_parts[locale_parts.length-1].length == 2) {
          locale_parts.pop();
          locale = locale_parts.join("_");
      }
      return locale;
  },
  /**
   * @function app.models.langstring.LocaleUtils.superLocale
   */
  superLocale: function(locale) {
      var pos = locale.lastIndexOf("_");
      if (pos > 0) {
          return locale.substr(0, pos);
      }
  },
  /**
   * @function app.models.langstring.LocaleUtils.localeAsTranslationService
   */
  localeAsTranslationService: function(locale) {
      var parts = locale.split("-x-mtfrom-");
      if (parts.length > 1) {
          return [this.localeAsTranslationService(parts[0]),
                  this.localeAsTranslationService(parts[1])].join("-x-mtfrom-");
      }
      var idiosyncrasies = this.translatorInfo['idiosyncrasies'] || {};
      if (idiosyncrasies[locale] !== undefined) {
          return idiosyncrasies[locale];
      } else {
          return locale;
      }
  },
  /**
   * @function app.models.langstring.LocaleUtils.getServiceShowOriginalString
   */
  getServiceShowOriginalString: function(){
    return this.translatorInfo["translation_notice"] || "";
  },
  /**
   * @function app.models.langstring.LocaleUtils.getServiceShowOriginalUrl
   */
  getServiceShowOriginalUrl: function(){
    return this.translatorInfo["translation_notice_url"] || "";
  },
};

/**
 * Lang string entry Model. A string in a given language. Many of those form a LangString
 * Frontend model for :py:class:`assembl.models.langstrings.LangStringEntry`
 * @class app.models.langstring.LangStringEntry
 * @extends app.models.base.BaseModel
 */
class LangStringEntry extends Base.Model.extend({
  /**
   * Defaults
   * @type {Object}
   */
  defaults: {
    "@type": Types.LANGSTRING_ENTRY,
    "@language": LocaleUtils.undefined,
    "error_count": 0,
    "error_code": undefined,
    "value": ""
  }
}) {
  /**
   * @function app.models.langstrings.LangStringEntry.isMachineTranslation
   */
  isMachineTranslation() {
    return this.get("@language").indexOf("-x-mtfrom-") > 0;
  }

  /**
   * @function app.models.langstrings.LangStringEntry.original
   */
  original() {
    // shortcut for original
    if (this.collection !== undefined && this.collection.langstring !== undefined) {
        return this.collection.langstring.original();
    }
    // WHY do we get here?
    return this;
  }

  /**
   * @function app.models.langstrings.LangStringEntry.langstring
   */
  langstring() {
    return this.collection.langstring;
  }

  /**
   * @function app.models.langstrings.LangStringEntry.value
   */
  value() {
    return this.get("value");
  }

  /**
   * @function app.models.langstrings.LangStringEntry.getLocaleValue
   */
  getLocaleValue() {
    return this.get('@language');
  }

  /**
   * @function app.models.langstrings.LangStringEntry.getBaseLocale
   */
  getBaseLocale() {
    var locale = this.get('@language');
    return locale.split("-x-mtfrom-")[0];
  }

  /**
   * @function app.models.langstrings.LangStringEntry.getBaseLocale
   */
  getTranslatedFromLocale() {
    if (this.isMachineTranslation()) {
      var locale = this.get('@language');
      return locale.split("-x-mtfrom-")[1];
    }
  }

  /**
   * @function app.models.langstrings.LangStringEntry.getOriginalLocale
   */
  getOriginalLocale() {
    if (this.isMachineTranslation()) {
      var locale = this.get('@language');
      return locale.split("-x-mtfrom-")[1];
    } else {
        return this.getBaseLocale();
    }
  }

  /**
   * @function app.models.langstrings.LangStringEntry.localeForService
   */
  localeForService() {
    return LocaleUtils.localeAsTranslationService(this.get("@language"));
  }

  /**
   * @function app.models.langstrings.LangStringEntry.applyFunction
   */
  applyFunction(func) {
    return new LangStringEntry({
      value: func(this.get("value")),
      "@language": this.get("@language")
    });
  }

  isEmptyStripped() {
    var value = this.get("value");
    if (!value) {
      return false;
    }
    value = Ctx.stripHtml(value);
    return !value;
  }
}

/**
 * Lang string entry collection
 * @class app.models.langstring.LangStringEntryCollection
 * @extends app.models.base.BaseCollection
 */
class LangStringEntryCollection extends Base.Collection.extend({
  /**
   * The model
   * @type {Account}
   */
  model: LangStringEntry
}) {
  /**
   * @member {string} app.models.langstrings.LangStringEntryCollection.url
   */
  url() {
    return this.langstring.url() + "/entries";
  }

  /**
   * @function app.models.langstrings.LangStringEntryCollection.initialize
   */
  initialize(models, options) {
    this.langstring = options ? options.langstring : null;
  }
}

/**
 * Lang string model. A multilingual string, composed of many LangStringEntry
 * Frontend model for :py:class:`assembl.models.langstrings.LangString`
 * @class app.models.langstring.LangString
 * @extends app.models.base.BaseModel
 */
class LangString extends Base.Model.extend({
  /**
   * Defaults
   * @type {Object}
   */
  defaults: {
    "@type": Types.LANGSTRING,
    entries: []
  }
}) {
  /**
   * @function app.models.langstrings.LangString.parse
   */
  parse(rawModel, options) {
    if ( _.isString(rawModel) ){
      var s = rawModel;
      rawModel = new LangString({
        entries: new LangStringEntryCollection([
          new LangStringEntry({
            "value": s,
            "@language": "und"
          })
        ])
      });
    }
    else if ( _.isNull(rawModel) || _.isUndefined(rawModel) || _.isEmpty(rawModel) ){
      rawModel = _.clone(LangString.empty);
    }
    else {
      rawModel.entries = new LangStringEntryCollection(rawModel.entries, {parse: true});
    }
    return rawModel;
  }

  /**
   * @member {string} app.models.langstrings.LangString.url
   */
  url() {
    return Ctx.getApiV2Url("LangString") + "/" + this.getNumericId();
  }

  /**
   * @function app.models.langstrings.LangString.initialize
   */
  initialize(attributes, options) {
    if (attributes && attributes.entries !== undefined) {
      attributes.entries.langstring = this;
    }
  }

  /**
   * @function app.models.langstrings.LangString.original
   */
  original() {
    var entries = this.get("entries");
    var originals = entries.filter(function(e) {return !e.isMachineTranslation();});
    if ( originals.length === 1 ){
      return originals[0];
    }
    else if (originals.length > 1) {
      return this.bestOf(originals);
    }
    else { // if ( originals.length == 0 ) {
      if ( entries.models && entries.models.length ){
        return entries.models[0];
      }
      return new LangStringEntry({
        "value": "",
        "@language": "zxx"
      });
    }
  }

  /**
   * Determines the best body string to use according to various settings
   * Get the best langStringEntry among those available using user prefs.
     1. Look at available original languages: get corresponding pref.
     2. Sort prefs (same order as original list.)
     3. take first applicable w/o trans or whose translation is available.
     4. if none, look at available translations and repeat.
     Logic is painful, but most of the time (single original) will be trivial in practice.
   * @param  {LangStringEntry.Collection}       available
   * @param  {LanguagePreference.Collection}    langPrefs
   * @param  {boolean}                          filter_errors   Used to supress errors
   * @param  {boolean}                          for_interface   To be used in interface, prefer discussion to user.
   * @returns {LangStringEntry}
   */
  bestOf(available, langPrefs, filter_errors, for_interface) {
    var i;
    var entry;
    var commonLenF;
    var that = this;
    if (!available || !available.length) {
        // this should never happen, need to look deeper;
        // but happens to body of SythesisPost
        return LangStringEntry.empty;
    }
    if (available.length == 1) {
        return available[0];
    }
    if (langPrefs !== undefined) {
      for (var useTranslationsC = 0; useTranslationsC < 2; useTranslationsC++) {
        var useTranslations = (useTranslationsC==1);
        var prefCandidates = [];
        var entryByPrefLocale = {};
        for (var i = 0; i < available.length; i++) {
          entry = available[i];
          var entry_locale = entry.get("@language");
          if (entry.isMachineTranslation() != useTranslations)
            continue;
          if (filter_errors && entry.get("error_code"))
            continue;
          var pref = langPrefs.getPreferenceForLocale(entry_locale);
          if (pref !== undefined) {
            entryByPrefLocale[pref.get("locale_code")] = entry;
            prefCandidates.push(pref);
          } else if (useTranslations) {
            // No pref for original, just return the original entry
            return entry;
          }
        }
        if (prefCandidates.length) {
          prefCandidates = _.sortBy(prefCandidates,
            (for_interface)?langPrefs.interface_comparator:langPrefs.comparator);
          for (i = 0; i < prefCandidates.length; i++) {
            var pref = prefCandidates[i];
            var translate_to = pref.get("translate_to_name");
            if (!translate_to) {
              return entryByPrefLocale[pref.get("locale_code")];
            } else {
              // take available with longest common locale string to translation target
              commonLenF = function(entry) {
                return LocaleUtils.localeCompatibility(entry.get("@language"), translate_to) !== false;
              };
              entry = _.max(available, commonLenF);
              if (commonLenF(entry) > 0) {
                return entry;
              }
            }
          }
        }
      }
    } else {
      console.error("No langPref");
    }
    // give up and give first original
    for (i = 0; i < available.length; i++) {
      entry = available[i];
      if (!entry.isMachineTranslation()) {
        return entry;
      }
    }
    // or first entry
    return available[0];
  }

  /**
   * @function app.models.langstrings.LangString.best
   */
  best(langPrefs) {
    return this.bestOf(this.get("entries").models, langPrefs);
  }

  /**
   * @function app.models.langstrings.LangString.bestValue
   */
  bestValue(langPrefs) {
    return this.best(langPrefs).get("value");
  }

  /**
   * Determines the best value, favouring interface over user prefs.
   * @function app.models.langstrings.LangString.bestValueInterface
   */
  bestValueInterface(langPrefs) {
    return this.bestOf(this.get("entries").models, langPrefs, false, true).get("value");
  }

  /**
   * Find the langstringEntry for a given language
   * @function app.models.langstrings.LangString.forLanguage
   */
  forLanguage(lang) {
    return this.get("entries").models.find(function (lse) {
      return lse.getBaseLocale() == lang;
    });
  }

  /**
   * Find the langstringEntry for the current interface, irrespective of user prefs
   * @function app.models.langstrings.LangString.forInterface
   */
  forInterface() {
    return this.forLanguage(Ctx.getLocale());
  }

  /**
   * Find the langstringEntry for the current interface, irrespective of user prefs
   * @function app.models.langstrings.LangString.forInterface
   */
  forInterfaceValue() {
    var lse = this.forInterface();
    return lse? lse.get('value') : null;
  }

  /**
   * @function app.models.langstrings.LangString.originalValue
   */
  originalValue() {
    return this.original().get("value");
  }

  /**
   * @function app.models.langstrings.LangString.bestWithErrors
   */
  bestWithErrors(langPrefs, filter_errors) {
    if (!langPrefs) {
      return {
        entry: this.original(),
        error: null
      };
    }
    var entry = this.bestOf(this.get("entries").models, langPrefs, filter_errors);
    var error_code = entry.get("error_code");
    if (error_code && entry !== undefined) {
      entry = entry.original();
    }
    return {
      entry: entry,
      error: error_code
    };
  }

  /**
   * @function app.models.langstrings.LangString.applyFunction
   */
  applyFunction(func) {
    var newEntries = this.get("entries").map(function(lse) {
      return lse.applyFunction(func);
    });
    return new LangString({
      "@id": this.id,
      entries: new LangStringEntryCollection(newEntries)
    });
  }

  isEmptyStripped(langPrefs) {
    var best = this.best(langPrefs);
    return !best || best.isEmptyStripped();
  }

  /**
   * Class method (call on prototype)
   * Initialize a langstring from a {locale: string} dictionary
   * @function app.models.langstrings.LangString.initFromDict
   */
  initFromDict(strdict) {
    var entries = this.get('entries');
    if (_.isArray(entries) || !_.isObject(entries)) {
      entries = new LangStringEntryCollection(entries, {parse: true});
      this.attributes.entries = entries;
    }
    if (strdict != undefined) {
      _.mapObject(strdict, function(v, k) {
        entries.add(new LangStringEntry({
          value: v,
          '@language': k
        }));
      });
    }
  }
}

LangStringEntry.empty = new LangStringEntry({
  value: '',
  '@language': 'zxx',
});

LangString.empty = new LangString({
  entries: new LangStringEntryCollection([LangStringEntry.empty]),
});

/**
 * Lang string collection
 * @class app.models.langstring.LangStringCollection
 * @extends app.models.base.BaseCollection
 */
class LangStringCollection extends Base.Collection.extend({
  /**
   * The model
   * @type {LangString}
   */
  model: LangString,

  /**
   * @member {string} app.models.langstrings.LangStringCollection.url
   */
  url: Ctx.getApiV2Url("LangString")
}) {
  /**
   * @function app.models.langstrings.LangStringCollection.parse
   */
  parse(rawModel, options) {
    rawModel.entries = new LangStringEntryCollection(rawModel.entries, {
        parse: true,
        langstring: this
    });
    return rawModel;
  }
}

export default {
  Model: LangString,
  Collection: LangStringCollection,
  EntryModel: LangStringEntry,
  EntryCollection: LangStringEntryCollection,
  LocaleUtils: LocaleUtils
};
