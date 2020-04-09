/**
 *
 * @module app.models.widget
 */

import _ from "underscore";

import Backbone from "backbone";
import BackboneSubset from "Backbone.Subset";
import Base from "./base.js";
import i18n from "../utils/i18n.js";
import Moment from "moment";
import Permissions from "../utils/permissions.js";
import Ctx from "../common/context.js";
import IdeaLoom from "../app.js";
import Types from "../utils/types.js";
import LangString from "../models/langstring.js";
import TokenVoteSessionView from "../views/tokenVoteSession.js";

/**
 * This represents a widget, a set of bundled functionality.
 * Frontend model for :py:class:`assembl.models.widgets.Widget`
 * @class app.models.widget.WidgetModel`
 * @extends app.models.base.BaseModel
 */
class WidgetModel extends Base.Model.extend({
    urlRoot: Ctx.getApiV2DiscussionUrl("/widgets"),

    defaults: {
        base_idea: null,
        start_date: null,
        end_date: null,
        activity_state: "active",
        discussion: null,
        settings: null,
        ui_endpoint: null,
        vote_specifications: null,
        hide_notification: false,
        "@id": null,
        "@type": null,
        "@view": null,
    },

    // this is a callback function which if set will replace the link (when the user clicks on the button)
    onButtonClick: null,

    MESSAGE_LIST_INSPIREME_CTX: 1,
    IDEA_PANEL_ACCESS_CTX: 2,
    IDEA_PANEL_CONFIGURE_CTX: 3,
    IDEA_PANEL_CREATE_CTX: 4,
    DISCUSSION_MENU_CONFIGURE_CTX: 5,
    DISCUSSION_MENU_CREATE_CTX: 6,
    VOTE_REPORTS: 7,
    TABLE_OF_IDEA_MARKERS: 8,
    INFO_BAR: 9,
    UNTIL_TEXT: 10,
}) {
    validate(attrs, options) {
        /**
         * check typeof variable
         * */
    }

    isRelevantForLink(linkType, context, idea) {
        return false;
    }

    findLink(idea) {
        var id = this.getId();
        var links = idea.get("widget_links");
        links = _.filter(links, function (link) {
            return link.widget == id;
        });
        if (links.length > 0) {
            return links[0]["@type"];
        }
    }

    isRelevantFor(context, idea) {
        if (idea === null) {
            return this.isRelevantForLink(null, context, null);
        }
        var that = this;
        var id = this.getId();
        var widgetLinks = idea.get("active_widget_links") || [];
        var postEndpoints = idea.get("widget_add_post_endpoint") || {};
        if (postEndpoints[id] !== undefined) {
            return true;
        }
        widgetLinks = _.filter(widgetLinks, function (link) {
            return (
                link.widget == id &&
                that.isRelevantForLink(link["@type"], context, idea)
            );
        });
        return widgetLinks.length > 0;
    }

    /*
  getBaseUriFor: function(widgetType) {
    switch (widgetType) {
      case "CreativitySessionWidget":
        return CreativitySessionWidgetModel.prototype.baseUri;
      case "MultiCriterionVotingWidget":
        return MultiCriterionVotingWidgetModel.prototype.baseUri;
      case "TokenVotingWidget":
        return TokenVotingWidgetModel.prototype.baseUri;
      case "InspirationWidget":
        return InspirationWidgetModel.prototype.baseUri;
      default:
        console.error("Widget.getBaseUriFor: wrong type");
    }
  },
  */

    /**
     * @function app.model.widgets.Widget.getObjectShareUrl
     * Get the URL of the sharing Widget, which has no backend
     * representation. TODO: move to Ctx?
     * @param  {dict} params parameters for the URL GET
     */
    getObjectShareUrl(params) {
        return Ctx.appendExtraURLParams(
            widget_url + "/share/index.html",
            params
        );
    }

    getCreationUrl(ideaId, locale) {
        console.error("Widget.getCreationUrl: wrong type");
    }

    getConfigurationUrl(targetIdeaId) {
        console.error("Widget.getConfigurationUrl: unknown type");
    }

    /**
     * @function app.model.widgets.Widget.getUrlForUser
     * get the URL that will launch the widget in a modal window.
     * @param  {string} targetIdeaId Id of an idea on which the widget was launched
     * @return {string}              URL
     */
    getUrlForUser(targetIdeaId, page) {
        // Is it the same as widget.get("ui_endpoint")?
        console.error("Widget.getUrlForUser: wrong type");
    }

    getCssClasses(context, idea) {
        return "";
    }

    getLinkText(context, idea) {
        return "";
    }

    getDescriptionText(context, idea, translationData) {
        return "";
    }

    // TODO?: Use context and targetIdeaId. But we don't need it yet.
    getShareUrl(context, targetIdeaId) {
        return Ctx.getAbsoluteURLFromDiscussionRelativeURL(
            "widget/" + encodeURIComponent(this.getId())
        );
    }

    getUrl(context, targetIdeaId, page) {
        switch (context) {
            case this.DISCUSSION_MENU_CREATE_CTX:
            case this.IDEA_PANEL_CREATE_CTX:
                return this.getCreationUrl(targetIdeaId);
            case this.IDEA_PANEL_CONFIGURE_CTX:
            case this.DISCUSSION_MENU_CONFIGURE_CTX:
                return this.getConfigurationUrl(targetIdeaId);
            case this.MESSAGE_LIST_INSPIREME_CTX:
            case this.IDEA_PANEL_ACCESS_CTX:
            case this.VOTE_REPORTS:
            case this.INFO_BAR:
                if (this.get("configured")) {
                    return this.getUrlForUser(targetIdeaId);
                } else {
                    return this.getConfigurationUrl(targetIdeaId);
                }
            case this.TABLE_OF_IDEA_MARKERS:
            default:
                console.error("Widget.getUrlForUser: wrong context");
        }
    }

    /**
     * Describes whether the widget model is internal to IdeaLoom
     * (using Marionette)(=false) or Independent (using Angular)(=true);
     * Override in child classes]
     * @returns {boolean}
     */
    isIndependentModalType() {
        return true;
    }

    showsButton(context, idea) {
        return true;
    }
}

/**
 * This represents a voting widget
 * Frontend model for :py:class:`assembl.models.widgets.VotingWidget`
 * @class app.models.widget.VotingWidgetModel`
 * @extends app.models.widget.WidgetModel
 */
class VotingWidgetModel extends WidgetModel.extend({
    baseUri: widget_url + "/vote/",

    defaults: {
        "@type": "MultiCriterionVotingWidget",
    },

    VOTE_STATUS_NONE: 0,
    VOTE_STATUS_INCOMPLETE: 1,
    VOTE_STATUS_COMPLETE: 2,
}) {
    getCreationUrl(ideaId, locale) {
        if (locale === undefined) {
            locale = Ctx.getLocale();
        }
        return (
            this.baseUri +
            "?admin=1&locale=" +
            locale +
            "#/admin/create_from_idea?idea=" +
            encodeURIComponent(ideaId + "?view=creativity_widget")
        );
    }

    getConfigurationUrl(targetIdeaId) {
        var base = this.baseUri;
        var uri = this.getId();
        var locale = Ctx.getLocale();
        base =
            base +
            "?admin=1&locale=" +
            locale +
            "#/admin/configure_instance?widget_uri=" +
            uri;
        if (targetIdeaId) {
            base += "&target=" + encodeURIComponent(targetIdeaId);
        }
        return base;
    }

    getUrlForUser(targetIdeaId, page) {
        var uri = this.getId();
        var locale = Ctx.getLocale();
        var currentUser = Ctx.getCurrentUser();
        var activityState = this.get("activity_state");

        var base =
            this.baseUri +
            "?config=" +
            encodeURIComponent(uri) +
            "&locale=" +
            locale;

        if (currentUser.isUnknownUser()) {
            return Ctx.getLoginURL() + "?"; // "?" is added in order to handle the hacky adding of "&locale=..." in infobar.tmpl
        }
        if (activityState == "ended") {
            base += "#/results"; // was "&page=results";
        }
        return base;
    }

    voteStatus() {
        var voteSpecs = this.get("vote_specifications");
        var voteCounts = _.map(voteSpecs, function (vs) {
            return (vs.my_votes || []).length;
        });
        var maxVoteCount = _.max(voteCounts);
        if (maxVoteCount === 0) {
            return this.VOTE_STATUS_NONE;
        }
        var minVoteCount = _.min(voteCounts);
        if (minVoteCount == this.get("votable_ideas", []).length) {
            return this.VOTE_STATUS_COMPLETE;
        }
        return this.VOTE_STATUS_INCOMPLETE;
    }

    getLinkText(context, idea) {
        var locale = Ctx.getLocale();
        var activityState = this.get("activity_state");
        var endDate = this.get("end_date");
        switch (context) {
            case this.IDEA_PANEL_CREATE_CTX:
                return i18n.gettext("Create a voting session on this idea");
            case this.INFO_BAR:
                if (this.get("configured")) {
                    return i18n.gettext("Vote");
                } else {
                    return i18n.gettext("Configure");
                }
            case this.IDEA_PANEL_ACCESS_CTX:
                if (!this.get("configured")) {
                    return i18n.gettext("Configure");
                }
                switch (activityState) {
                    case "active":
                        switch (this.voteStatus()) {
                            case this.VOTE_STATUS_NONE:
                                return i18n.gettext("Vote");
                            case this.VOTE_STATUS_INCOMPLETE:
                                return i18n.gettext("Complete your vote");
                            case this.VOTE_STATUS_COMPLETE:
                                return i18n.gettext("Modify your vote");
                        }
                    case "ended":
                        return i18n.gettext("See the vote results");
                }
            case this.IDEA_PANEL_CONFIGURE_CTX:
                return i18n.gettext("Configure this vote widget");
            case this.VOTE_REPORTS:
                if (activityState == "ended") {
                    return (
                        i18n.gettext("See results from the vote of ") +
                        Moment(endDate).fromNow()
                    );
                }
        }
        return "";
    }

    getCssClasses(context, idea) {
        var currentUser = Ctx.getCurrentUser();
        if (currentUser.isUnknownUser()) {
            return "";
        }
        switch (context) {
            case this.INFO_BAR:
                return "js_openTargetInModal";
            case this.IDEA_PANEL_ACCESS_CTX:
                switch (this.get("activity_state")) {
                    case "active":
                        return "btn-primary js_openTargetInModal";
                    case "ended":
                        return "btn-secondary js_openTargetInModal";
                }
        }
        return "";
    }

    showsButton(context, idea) {
        switch (context) {
            case this.INFO_BAR:
                var currentUser = Ctx.getCurrentUser();
                return currentUser.can(Permissions.VOTE);
        }
        return true;
    }

    getDescriptionText(context, idea, translationData) {
        var locale = Ctx.getLocale();
        var currentUser = Ctx.getCurrentUser();
        var activityState = this.get("activity_state");
        var endDate = this.get("end_date");
        if (!this.get("configured")) {
            if (context == this.UNTIL_TEXT) {
                return "";
            }
            return i18n.gettext("This vote widget is not fully configured");
        }
        switch (context) {
            case this.INFO_BAR:
                var message = i18n.gettext("A voting session has started.");
                if (endDate) {
                    message +=
                        " " +
                        this.getDescriptionText(
                            this.UNTIL_TEXT,
                            idea,
                            translationData
                        );
                }
                if (!currentUser.can(Permissions.VOTE)) {
                    // TODO: get the current discussion synchronously.
                    message +=
                        "  " +
                        i18n.sprintf(
                            i18n.gettext(
                                "You cannot vote right now because %s."
                            ),
                            currentUser.getRolesMissingMessageForPermission(
                                Permissions.VOTE
                            )
                        );
                }
                return message;
            case this.IDEA_PANEL_ACCESS_CTX:
                var link = this.findLink(idea) || "";
                switch (link + "_" + activityState) {
                    case "VotedIdeaWidgetLink_active":
                    case "VotableIdeaWidgetLink_active":
                        return i18n.sprintf(
                            i18n.gettext(
                                "The option “%s” is being considered in a vote"
                            ),
                            idea.getShortTitleSafe(translationData)
                        );
                    case "VotedIdeaWidgetLink_ended":
                    case "VotableIdeaWidgetLink_ended":
                        return i18n.sprintf(
                            i18n.gettext(
                                "The option “%s” was considered in a vote"
                            ),
                            idea.getShortTitleSafe(translationData)
                        );
                    case "BaseIdeaWidgetLink_active":
                        return i18n.gettext(
                            "A voting session is ongoing on this issue"
                        );
                    case "BaseIdeaWidgetLink_ended":
                        return i18n.gettext(
                            "A voting session has happened on this issue"
                        );
                    case "VotingCriterionWidgetLink_active":
                        return i18n.sprintf(
                            i18n.gettext(
                                "“%s” is being used as a criterion in a vote"
                            ),
                            idea.getShortTitleSafe(translationData)
                        );
                    case "VotingCriterionWidgetLink_ended":
                        return i18n.sprintf(
                            i18n.gettext(
                                "“%s” was used as a criterion in a vote"
                            ),
                            idea.getShortTitleSafe(translationData)
                        );
                }
                break;
            case this.UNTIL_TEXT:
                switch (activityState) {
                    case "ended":
                        return "";
                        break;
                    default:
                        if (endDate) {
                            return i18n.sprintf(
                                i18n.gettext("You have %s to vote"),
                                Moment(endDate).fromNow(true)
                            );
                        }
                }
                break;
        }
        return "";
    }

    isRelevantForLink(linkType, context, idea) {
        // TODO: This should depend on widget configuration.
        var activityState = this.get("activity_state");

        var currentUser = Ctx.getCurrentUser();
        if (
            !this.get("configured") &&
            !currentUser.can(Permissions.ADMIN_DISCUSSION)
        ) {
            return false;
        }
        switch (context) {
            case this.INFO_BAR:
                return (
                    activityState === "active" &&
                    !this.get("closeInfobar") &&
                    !this.get("hide_notification") &&
                    this.voteStatus() != this.VOTE_STATUS_COMPLETE
                );
            case this.IDEA_PANEL_ACCESS_CTX:
                // assume non-root idea, relevant widget type
                return (
                    activityState == "ended" ||
                    currentUser.can(Permissions.VOTE)
                );
            case this.IDEA_PANEL_CONFIGURE_CTX:
                return true;
            case this.VOTE_REPORTS:
                return activityState === "ended";
            case this.TABLE_OF_IDEA_MARKERS:
                return (
                    linkType === "BaseIdeaWidgetLink" &&
                    activityState === "active" &&
                    currentUser.can(Permissions.VOTE)
                );
            default:
                return false;
        }
    }
}

/**
 * This represents a multi-criterion voting widget
 * Frontend model for :py:class:`assembl.models.widgets.MultiCriterionVotingWidgetModel`
 * @class app.models.widget.MultiCriterionVotingWidgetModel`
 * @extends app.models.widget.VotingWidgetModel
 */
class MultiCriterionVotingWidgetModel extends VotingWidgetModel.extend({
    defaults: {
        "@type": "MultiCriterionVotingWidget",
    },
}) {
    getLinkText(context, idea) {
        switch (context) {
            case this.IDEA_PANEL_CREATE_CTX:
                return i18n.gettext(
                    "Create a multi-criterion voting session on this idea"
                );
            default:
                return super.getLinkText(...arguments);
        }
    }
}

/**
 * This represents a token voting voting widget
 * Frontend model for :py:class:`assembl.models.widgets.TokenVotingWidgetModel`
 * @class app.models.widget.TokenVotingWidgetModel`
 * @extends app.models.widget.VotingWidgetModel
 */
class TokenVotingWidgetModel extends VotingWidgetModel.extend({
    defaults: {
        "@type": "TokenVotingWidget",
    },
}) {
    constructor() {
        super(...arguments);
        this.on("buttonClick", this.onButtonClick);
        this.on("showResult", this.onShowResult);
    }

    getCreationUrl(ideaId, locale) {
        if (locale === undefined) {
            locale = Ctx.getLocale();
        }
        return (
            this.baseUri +
            "?admin=1&locale=" +
            locale +
            "#/admin/create_from_idea?idea=" +
            encodeURIComponent(ideaId + "?view=creativity_widget") +
            "&widget_type=TokenVotingWidget"
        );
    }

    getLinkText(context, idea) {
        switch (context) {
            case this.IDEA_PANEL_CREATE_CTX:
                return i18n.gettext(
                    "Create a token voting session on this idea"
                );
                break;
            case this.INFO_BAR:
                if (this.get("configured")) {
                    return i18n.gettext("Vote");
                } else {
                    return i18n.gettext("Configure");
                }
                break;
            default:
                return super.getLinkText(...arguments);
        }
    }

    getUrlForUser(targetIdeaId, page) {
        //var uri = this.getId();
        //var locale = Ctx.getLocale();
        var currentUser = Ctx.getCurrentUser();
        var activityState = this.get("activity_state");
        //var base = this.baseUri + "?config=" + encodeURIComponent(uri) + "&locale=" + locale;
        var base = this.getShareUrl();
        if (currentUser.isUnknownUser()) {
            return Ctx.getLoginURL() + "?"; // "?" is added in order to handle the hacky adding of "&locale=..." in infobar.tmpl
        }
        if (activityState == "ended") {
            base += "/results";
        }
        return base;
    }

    // FIXME: Having view code in a model is probably not a good idea. How could we do better?
    onButtonClick(evt) {
        console.log("TokenVotingWidgetModel::onButtonClick() evt: ", evt);
        if (evt && _.isFunction(evt.preventDefault)) {
            evt.preventDefault();
        }

        var that = this;
        var activityState = that.get("activity_state");
        //var configured = that.get("configured");

        switch (activityState) {
            case "active":
                var modalView = new TokenVoteSessionView.TokenVoteSessionModal({
                    model: that,
                });

                Ctx.setCurrentModalView(modalView);
                IdeaLoom.rootView.showChildView("slider", modalView);
                break;
            case "ended":
                that.onShowResult();
                break;
        }
    }

    /*
    For debugging results view purposes
   */
    onShowResult(evt) {
        var modalView = new TokenVoteSessionView.TokenVoteSessionResultModal({
            model: this,
        });
        Ctx.setCurrentModalView(modalView);
        IdeaLoom.rootView.showChildView("slider", modalView);
    }

    getCssClasses(context, idea) {
        var currentUser = Ctx.getCurrentUser();
        if (currentUser.isUnknownUser()) {
            return "";
        }
        switch (context) {
            case this.INFO_BAR:
                if (this.get("configured")) {
                    return "";
                } else {
                    return "js_openTargetInModal";
                }
                break;
            case this.IDEA_PANEL_ACCESS_CTX:
                switch (this.get("activity_state")) {
                    case "active":
                        if (this.get("configured")) {
                            return "btn-primary";
                        }
                        return "btn-primary js_openTargetInModal";
                    case "ended":
                        if (this.get("configured")) {
                            return "btn-primary";
                        }
                        return "btn-secondary js_openTargetInModal";
                }
                break;
        }
        return "";
    }

    isIndependentModalType() {
        return false;
    }

    /**
     * @returns {Model|null} Returns a new VoteSpec Model (if present) or null
     */
    getVoteSpecificationModel() {
        var specs = this.get("vote_specifications");
        if (specs && specs.length > 0) {
            //Assumes only one tokenVoteSpecification exists in this widget.
            var tokenSpec = _.findWhere(specs, {
                "@type": Types.TOKENVOTESPECIFICATION,
            });
            if (tokenSpec) {
                return new TokenVoteSpecificationModel(tokenSpec, {
                    parse: true,
                    widgetModel: this,
                });
            } else return null;
        } else return null;
    }

    voteStatus() {
        // Should we also consider probably badly configured widgets? For example a widget where the user cannot allocate all his tokens? (this is a widget where a category matches this condition: votable_ideas.length * category.max_per_idea < category.total_number)
        var voteSpecs = _.where(this.get("vote_specifications"), {
            "@type": "TokenVoteSpecification",
        });
        var status = this.VOTE_STATUS_INCOMPLETE;
        for (var i = 0; i < voteSpecs.length; ++i) {
            var voteSpec = voteSpecs[i];
            var isExclusive =
                "exclusive_categories" in voteSpec
                    ? voteSpec.exclusive_categories
                    : false;
            var myVotes = "my_votes" in voteSpec ? voteSpec.my_votes : null;
            var categories =
                "token_categories" in voteSpec
                    ? voteSpec.token_categories
                    : null;
            if (!myVotes || !myVotes.length) {
                return this.VOTE_STATUS_INCOMPLETE;
            }
            //if ( isExclusive ){
            // Should it behave differently? For example, we could say we don't display hellobar if voter has already used all his positive tokens, even if he has not used all his negative tokens.
            //}
            //else {
            var votesPerCategory = _.groupBy(myVotes, "token_category");
            var tokensUsedPerCategory = _.mapObject(votesPerCategory, function (
                val,
                key
            ) {
                return _.reduce(
                    val,
                    function (memo, num) {
                        return memo + ("value" in num ? num.value : 0);
                    },
                    0
                );
            });
            var someTokenCategoriesHaveUnusedTokens = _.findKey(
                tokensUsedPerCategory,
                function (val, key) {
                    var category = _.findWhere(categories, { "@id": key });
                    if (!category) {
                        return false;
                    }
                    var total =
                        "total_number" in category
                            ? category.total_number
                            : null;
                    if (!total) {
                        return false;
                    }
                    return val < total;
                }
            );
            if (someTokenCategoriesHaveUnusedTokens) {
                return this.VOTE_STATUS_INCOMPLETE;
            }
            //}
        }
        return this.VOTE_STATUS_COMPLETE;
    }
}

/**
 * The specifications describing how a vote should happen
 * Frontend model for :py:class:`assembl.models.votes.TokenVoteSpecification`
 * @class app.models.widget.TokenVoteSpecificationModel
 * @extends app.models.base.BaseModel
 */
class TokenVoteSpecificationModel extends Base.Model.extend({
    defaults: {
        "@type": Types.TOKENVOTESPECIFICATION,
        token_categories: [],
        exclusive_categories: null,
        settings: null,
        results_url: null,
    },
}) {
    getVoteResultUrl() {
        var url = this.get("results_url");
        if (url) {
            // var trim = /(?:^\w+:Discussion\/\d+)(.+)/.exec(url)[1];
            return Ctx.getUrlFromUri(url);
        }
    }

    parse(raw, options) {
        if (
            _.has(raw, "token_categories") &&
            _.isArray(raw["token_categories"])
        ) {
            raw.token_categories = new TokenCategorySpecificationCollection(
                raw.token_categories,
                { parse: true }
            );
        }
        return raw;
    }
}

/**
 * The specifications describing a token category
 * Frontend model for :py:class:`assembl.models.votes.TokenCategorySpecification`
 * @class app.models.widget.TokenCategorySpecificationModel
 * @extends app.models.base.BaseModel
 */
class TokenCategorySpecificationModel extends Base.Model.extend({
    defaults: {
        name: null, // (LangString) the display/translated name of the token category. Example: "Positive"
        typename: null, // (string) identifier name of the token category. Categories with the same name can be compared.
        total_number: null, // (integer) number of available tokens in the bag, that the voter can allocate on several candidates
        token_vote_specification: null, // (string) the id of a token vote spec this category is associated to
        image: null, // (string) URL of an image of a token
        image_empty: null,
        maximum_per_idea: null, // (integer) maximum number of tokens a voter has the right to put on an idea
        color: null,
        "@type": "TokenCategorySpecification",
        "@view": "voting_widget",
    },
}) {
    parse(rawModel, options) {
        rawModel.name = new LangString.Model(rawModel.name, { parse: true });
        return rawModel;
    }
}

class TokenCategorySpecificationCollection extends Base.Collection.extend({
    model: TokenCategorySpecificationModel,
}) {
    /*
    The URL is rarely used to get this collection. It's taken from the Token Specification Model
   */
    url() {
        return Ctx.getApiV2DiscussionUrl(
            "widgets/" + this.widgetModel.id + "/vote_specifications"
        );
    }

    initialize(options) {
        this.widgetModel = options.widgetModel;
    }
}

/*
  This model represents global voting results, as generated by
  :py:meth:assembl.models.votes.AbstractVoteSpecification.voting_results
  It is not symmetrical to the back-end key-value hash
  There is no back-end model for the vote results
  This is for view purposes only (read-only)
  Do not create the model; create the collection instead!
 * @class app.models.widget.VoteResultModel
 * @extends app.models.base.BaseModel
 */
class VoteResultModel extends Base.Model.extend({
    defaults: {
        nums: null,
        sums: null,
        n: null,
        idea_id: null,
        objectConnectedTo: null,
        objectDescription: null,
        n_voters: null,
    },
}) {
    getNumberOfVoters() {
        return this.get("n_voters");
    }

    /**
     * @param  {string} category      [The category typename]
     * @returns {Number|null}
     */
    getTotalVotesForCategory(category) {
        var sums = this.get("sums");
        if (_.has(sums, category)) {
            return sums[category];
        } else return null;
    }
}

class VoteResultCollection extends Base.Collection.extend({
    model: VoteResultModel,
}) {
    url() {
        return this.tokenSpecModel.getVoteResultUrl();
    }

    initialize(options) {
        this.widgetModel = options.widgetModel;
        this.tokenSpecModel = this.widgetModel.getVoteSpecificationModel();
        this.sortAscending = false;
        this.sortSpecName = this.tokenSpecModel
            .get("token_categories")
            .models[0].get("typename");
    }

    comparator(model) {
        var sums = model.get("sums") || {};
        return (this.sortAscending ? 1 : -1) * (sums[this.sortSpecName] || 0);
    }

    /*
    The returned data from the API is a key-value dict of idea_id: results,
    must convert to an Array of objects.
   */
    parse(rawModel) {
        return _.chain(rawModel)
            .keys(rawModel)
            .filter(function (key) {
                return key !== "n_voters";
            })
            .map(function (idea) {
                var newObj = rawModel[idea];
                newObj.idea_id = idea;
                //Data duplication
                newObj.n_voters = rawModel["n_voters"];
                return newObj;
            })
            .value();
    }

    /**
     * Method that associates the idea Model to the appropriate
     * @param  {Object} objectCollection  Ideas Collection
     * @returns {undefined}
     */
    associateIdeaModelToObject(objectCollection) {
        //Add checks to ensure that the idea is not removed!
        this.each(function (result) {
            var ideaModel = objectCollection.findWhere({
                "@id": result.get("idea_id"),
            });
            result.set("objectConnectedTo", ideaModel);
        });
    }

    /**
     * Associates the Token Specification Category Collection to each result model
     * @param  {Object} categoryCollection  Collection of Token Specification Category Collection
     * @returns {undefined}
     */
    associateCategoryModelToObject(categoryCollection) {
        //Add checks to ensure that the category collection is removed
        this.each(function (result) {
            result.set("objectDescription", categoryCollection);
        });
    }

    associateTo(ideaCollection, specificationModel) {
        this.associateIdeaModelToObject(ideaCollection);
        this.associateCategoryModelToObject(
            specificationModel.get("token_categories")
        );
    }

    getNumberOfVoters() {
        return this.at(0).getNumberOfVoters();
    }

    /**
     * @param  {string} category  [The category typename]
     * @returns {Number|null}
     */
    getTotalVotesForCategory(category) {
        return this.reduce(function (memo, model, index) {
            var val = model.getTotalVotesForCategory(category);
            return val !== null ? memo + val : memo;
        }, 0);
    }

    /**
     * Method that returns a key:value object that describes
     * the total number of votes per category, keyed by category typename
     * @returns {Object}
     */
    getTotalVotesByCategories() {
        //First, get the list of categories, which is found in every model (yes, poor design, I know...)
        var categories = this.at(0)
            .get("objectDescription")
            .map(function (categoryModel) {
                return categoryModel.get("typename");
            });

        var sums = _.map(
            categories,
            function (categName) {
                return this.map(function (result) {
                    return result.get("sums")[categName] || 0;
                });
            },
            this
        );

        var sumTokens = _.map(sums, function (s) {
            return _.reduce(s, function (a, b) {
                return a + b;
            });
        });

        return _.object(_.zip(categories, sumTokens));
    }

    /**
     * [Returns the following statistics regarding the results collection
     *   {
     *     sums: {Array<Array>} //Collection of Arrays of tokens voted per category
     *     sumTokens: {Array<Number>} //Array of tokens voted per category
     *     maxTokens: Array<Number> //Array of maximum number of tokens voted per category
     *     percents: Array<Number> //Array of maximum number of tokens voted per category, as percent
     *     maxPercent: Number //maximum number of tokens voted, as percent
     *   }
     * ]
     * @returns {Object}
     */
    getStatistics() {
        //First, get the list of categories, which is found in every model (yes, poor design, I know...)
        var categories = this.at(0);
        if (categories) {
            categories = this.at(0)
                .get("objectDescription")
                .map(function (categoryModel) {
                    return categoryModel.get("typename");
                });
        } else {
            categories = [];
        }

        // Compute the number of tokens spent by category,
        // and for each category, the maximum percent of tokens
        // that were spent on any one idea. This maxPercent will
        // be used for scaling.
        // Note that we could also have scaled not on tokens spent,
        // but tokens spendable (given number of voters * max tokens.)
        // TODO: We should code both approaches and compare at some point.

        var sums = _.map(
            categories,
            function (categName) {
                return this.map(function (result) {
                    return result.get("sums")[categName] || 0;
                });
            },
            this
        );

        var maxTokens = _.map(sums, function (s) {
            return Math.max.apply(null, s);
        });

        var sumTokens = _.map(sums, function (s) {
            return _.reduce(s, function (a, b) {
                return a + b;
            });
        });

        var percents = _.map(_.zip(maxTokens, sumTokens), function (x) {
            return x[1] ? x[0] / x[1] : 0;
        });

        var maxPercent = Math.max.apply(null, percents);
        var catSummary = _.object(_.zip(categories, sumTokens));
        var numVoters = this.getNumberOfVoters();

        return {
            sums: sums,
            maxTokens: maxTokens,
            sumTokens: sumTokens,
            percents: percents,
            maxPercent: maxPercent,
            categorySummary: catSummary,
            numVoters: numVoters,
        };
    }
}

/**
 * This model represents a single vote of a user on an idea.
 * Frontend model for :py:class:`assembl.models.votes.AbstractIdeaVote`
 * @class app.models.widget.IdeaVoteModel
 * @extends app.models.base.BaseModel
 */
class IdeaVoteModel extends Base.Model.extend({
    defaults: {
        token_category: null,
    },
}) {}

/**
 * This model represents a single token vote of a user on an idea.
 * Frontend model for :py:class:`assembl.models.votes.TokenIdeaVote`
 * @class app.models.widget.TokenIdeaVoteModel
 * @extends app.models.widget.IdeaVoteModel
 */
class TokenIdeaVoteModel extends IdeaVoteModel.extend({
    defaults: {
        idea: null,
        criterion: null,
        widget: null,
        value: null,
        original_uri: null,
        vote_spec: null,
        voter: null,
    },
}) {}

class TokenIdeaVoteCollection extends Base.Collection.extend({
    model: TokenIdeaVoteModel,
}) {
    getTokenBagDataForCategory(tokenCategory) {
        // TODO: cache results until collection content changes
        var myVotesCollection = this;
        var myVotesInThisCategory = myVotesCollection.where({
            token_category: tokenCategory.get("@id"),
        });
        var myVotesValues = _.map(myVotesInThisCategory, function (vote) {
            return vote.get("value");
        });
        var myVotesCount = _.reduce(
            myVotesValues,
            function (memo, num) {
                return memo + num;
            },
            0
        );
        var total = tokenCategory.get("total_number");
        return {
            total_number: total,
            my_votes_count: myVotesCount,
            remaining_tokens: total - myVotesCount,
        };
    }
}

/**
 * Represents a Creativity Session Widget
 * Frontend model for :py:class:`assembl.models.widgets.CreativitySessionWidget`
 * @class app.models.widget.CreativitySessionWidgetModel`
 * @extends app.models.widget.WidgetModel
 */
class CreativitySessionWidgetModel extends WidgetModel.extend({
    baseUri: widget_url + "/session/",

    defaults: {
        "@type": "CreativitySessionWidget",
        num_posts_by_current_user: 0,
    },
}) {
    getCreationUrl(ideaId, locale) {
        if (locale === undefined) {
            locale = Ctx.getLocale();
        }
        return (
            this.baseUri +
            "#/admin/create_from_idea?admin=1&locale=" +
            locale +
            "&idea=" +
            encodeURIComponent(ideaId) +
            "&view=creativity_widget"
        );
    }

    getConfigurationUrl(targetIdeaId) {
        var base = this.baseUri;
        var uri = this.getId();
        var locale = Ctx.getLocale();
        return base + "?locale=" + locale + "#/home?admin=1&config=" + uri;
    }

    getUrlForUser(targetIdeaId, page) {
        var base = this.baseUri;
        var uri = this.getId();
        var locale = Ctx.getLocale();
        if (!targetIdeaId) {
            if (this.get("base_idea")) {
                targetIdeaId = this.get("base_idea")["@id"];
            }
        }
        if (!targetIdeaId) {
            targetIdeaId = null;
        }

        return (
            base +
            "?locale=" +
            locale +
            "#/home?config=" +
            encodeURIComponent(uri) +
            "&target=" +
            encodeURIComponent(targetIdeaId)
        );
    }

    getLinkText(context, idea) {
        var locale = Ctx.getLocale();
        var activityState = this.get("activity_state");
        switch (context) {
            case this.IDEA_PANEL_CREATE_CTX:
                return i18n.gettext("Create a creativity session on this idea");
            case this.INFO_BAR:
                if (this.get("configured")) {
                    return i18n.gettext("Participate");
                } else {
                    return i18n.gettext("Configure");
                }
            case this.IDEA_PANEL_CONFIGURE_CTX:
            case this.DISCUSSION_MENU_CONFIGURE_CTX:
                // assume non-root idea, relevant widget type
                return i18n.gettext(
                    "Configure the creativity session on this idea"
                );
            case this.IDEA_PANEL_ACCESS_CTX:
                if (!this.get("configured")) {
                    return i18n.gettext("Configure");
                }
                switch (activityState) {
                    case "active":
                        return i18n.gettext("Participate");
                    case "ended":
                        return i18n.gettext("Review the session");
                }
        }
        return "";
    }

    getCssClasses(context, idea) {
        switch (context) {
            case this.INFO_BAR:
                return "js_openTargetInModal";
            case this.IDEA_PANEL_ACCESS_CTX:
                switch (this.get("activity_state")) {
                    case "active":
                        return "btn-primary js_openTargetInModal";
                    case "ended":
                        return "btn-secondary js_openTargetInModal";
                }
        }
        return "";
    }

    getDescriptionText(context, idea, translationData) {
        var locale = Ctx.getLocale();
        var activityState = this.get("activity_state");
        var endDate = this.get("end_date");
        if (!this.get("configured")) {
            if (context == this.UNTIL_TEXT) {
                return "";
            }
            return i18n.gettext("This widget is not fully configured");
        }
        switch (context) {
            case this.INFO_BAR:
                var message = i18n.gettext("A creativity session is ongoing.");
                if (endDate) {
                    message +=
                        " " +
                        this.getDescriptionText(
                            this.UNTIL_TEXT,
                            idea,
                            translationData
                        );
                }
                return message;
            case this.IDEA_PANEL_ACCESS_CTX:
                switch (activityState) {
                    case "active":
                        return i18n.gettext(
                            "A creativity session is ongoing on this issue"
                        );
                    case "ended":
                        return i18n.gettext(
                            "A creativity session has happened on this issue"
                        );
                }
            case this.UNTIL_TEXT:
                if (endDate) {
                    return i18n.sprintf(
                        i18n.gettext("You have %s to participate"),
                        Moment(endDate).fromNow(true)
                    );
                }
        }
        return "";
    }

    isRelevantForLink(linkType, context, idea) {
        // TODO: This should depend on widget configuration.
        var activityState = this.get("activity_state");

        var currentUser = Ctx.getCurrentUser();
        if (
            !this.get("configured") &&
            !currentUser.can(Permissions.ADMIN_DISCUSSION)
        ) {
            return false;
        }
        switch (context) {
            case this.INFO_BAR:
                return (
                    activityState === "active" &&
                    !this.get("closeInfobar") &&
                    !this.get("hide_notification") &&
                    currentUser.can(Permissions.ADD_POST) &&
                    this.get("num_posts_by_current_user", 0) === 0
                );
            case this.IDEA_PANEL_CONFIGURE_CTX:
            case this.DISCUSSION_MENU_CONFIGURE_CTX:
                // assume non-root idea, relevant widget type
                return linkType === "IdeaCreativitySessionWidgetLink";
            case this.IDEA_PANEL_ACCESS_CTX:
            case this.TABLE_OF_IDEA_MARKERS:
                return (
                    linkType == "IdeaCreativitySessionWidgetLink" &&
                    activityState === "active" &&
                    currentUser.can(Permissions.ADD_POST)
                );
            default:
                return false;
        }
    }
}

class InspirationWidgetModel extends WidgetModel.extend({
    baseUri: widget_url + "/creativity/",

    defaults: {
        "@type": "InspirationWidget",
    },
}) {
    getCreationUrl(ideaId, locale) {
        if (locale === undefined) {
            locale = Ctx.getLocale();
        }
        return (
            this.baseUri +
            "?admin=1&locale=" +
            locale +
            "#/admin/create_from_idea?idea=" +
            encodeURIComponent(ideaId + "?view=creativity_widget")
        );
    }

    getConfigurationUrl(targetIdeaId) {
        var base = this.baseUri;
        var uri = this.getId();
        var locale = Ctx.getLocale();
        base =
            base +
            "?admin=1&locale=" +
            locale +
            "#/admin/configure_instance?widget_uri=" +
            Ctx.getUrlFromUri(uri);
        if (targetIdeaId) {
            base += "&target=" + encodeURIComponent(targetIdeaId);
        }
        return base;
    }

    getUrlForUser(targetIdeaId, page) {
        var id = this.getId();
        var locale = Ctx.getLocale();
        var url =
            this.baseUri +
            "?config=" +
            encodeURIComponent(Ctx.getUrlFromUri(id)) +
            "&locale=" +
            locale;
        if (targetIdeaId !== undefined) {
            url += "&target=" + encodeURIComponent(targetIdeaId);
        }
        return url;
    }

    getLinkText(context, idea) {
        var locale = Ctx.getLocale();
        var activityState = this.get("activity_state");
        switch (context) {
            case this.IDEA_PANEL_CREATE_CTX:
                return i18n.gettext(
                    "Create an inspiration module on this idea"
                );
            case this.DISCUSSION_MENU_CREATE_CTX:
                return i18n.gettext(
                    "Create an inspiration module on this discussion"
                );
            case this.DISCUSSION_MENU_CONFIGURE_CTX:
                return i18n.gettext(
                    "Configure the inspiration module associated to the discussion"
                );
            case this.IDEA_PANEL_CONFIGURE_CTX:
                return i18n.gettext(
                    "Configure the inspiration module associated to this idea"
                );
            case this.IDEA_PANEL_ACCESS_CTX:
                if (this.get("configured")) {
                    return i18n.gettext("I need inspiration");
                } else {
                    return i18n.gettext("Configure");
                }
        }
        return "";
    }

    isRelevantForLink(linkType, context, idea) {
        // TODO: This should depend on widget configuration.
        // Put in subclasses?
        var activityState = this.get("activity_state");

        var currentUser = Ctx.getCurrentUser();
        if (
            !this.get("configured") &&
            !currentUser.can(Permissions.ADMIN_DISCUSSION)
        ) {
            return false;
        }
        switch (context) {
            case this.MESSAGE_LIST_INSPIREME_CTX:
                return activityState === "active" && this.get("configured");
            case this.DISCUSSION_MENU_CONFIGURE_CTX:
            case this.IDEA_PANEL_CONFIGURE_CTX:
                // assume root idea
                return linkType === "IdeaInspireMeWidgetLink";
            default:
                return false;
        }
    }
}

var localWidgetClassCollection = new Base.Collection([
    new MultiCriterionVotingWidgetModel(),
    new TokenVotingWidgetModel(),
    new CreativitySessionWidgetModel(),
    new InspirationWidgetModel(),
]);

var globalWidgetClassCollection = new Base.Collection([
    new InspirationWidgetModel(),
]);

// begin see https://github.com/jashkenas/backbone/commit/d1de6e89117f02adfa0f4ba05b9cf6ba3f2ecfb7
var WidgetFactory = function (attrs, options) {
    switch (attrs["@type"]) {
        case "InspirationWidget":
            return new InspirationWidgetModel(attrs, options);
        case "MultiCriterionVotingWidget":
            return new MultiCriterionVotingWidgetModel(attrs, options);
        case "TokenVotingWidget":
            return new TokenVotingWidgetModel(attrs, options);
        case "CreativitySessionWidget":
            return new CreativitySessionWidgetModel(attrs, options);
        default:
            console.error("Unknown widget type:" + attrs["@type"]);
            return new WidgetModel(attrs, options);
    }
};
WidgetFactory.prototype.idAttribute = Base.Model.prototype.idAttribute;

// end see https://github.com/jashkenas/backbone/commit/d1de6e89117f02adfa0f4ba05b9cf6ba3f2ecfb7

class WidgetCollection extends Base.Collection.extend({
    url: Ctx.getApiV2DiscussionUrl("/widgets"),
    model: WidgetFactory,
}) {
    relevantWidgetsFor(idea, context) {
        return this.filter(function (widget) {
            return widget.isRelevantFor(context, idea);
        });
    }

    getCreationUrlForClass(cls, ideaId, locale) {
        if (locale === undefined) {
            locale = Ctx.getLocale();
        }
        switch (cls) {
            case "InspirationWidget":
                return InspirationWidgetModel.getCreationUrl();
            case "MultiCriterionVotingWidget":
                return MultiCriterionVotingWidgetModel.getCreationUrl();
            case "TokenVotingWidget":
                return TokenVotingWidgetModel.getCreationUrl();
            case "CreativitySessionWidget":
                return CreativitySessionWidgetModel.getCreationUrl();
            default:
                console.error(
                    "WidgetCollection.getCreationUrlForClass: wrong widget class"
                );
        }
    }

    configurableWidgetsUris(context) {
        switch (context) {
            case WidgetModel.DISCUSSION_MENU_CONFIGURE_CTX:
                return [this.getCreationUrlForClass("InspirationWidget")];
            case WidgetModel.IDEA_PANEL_CONFIGURE_CTX:
                return [
                    this.getCreationUrlForClass("CreativitySessionWidget"),
                    this.getCreationUrlForClass("MultiCriterionVotingWidget"),
                    this.getCreationUrlForClass("TokenVotingWidget"),
                    this.getCreationUrlForClass("InspirationWidget"),
                ];
            default:
                console.error(
                    "WidgetCollection.configurableWidgetsUris: wrong context"
                );
        }
    }

    relevantUrlsFor(idea, context) {
        // Also give strings...
        // Careful about permissions!
        var widgets = this.relevantWidgetsFor(idea, context);

        var ideaId = idea.getId();
        return _.map(widgets, function (w) {
            return w.getUrl(context, ideaId);
        });
    }
}

class ActiveWidgetCollection extends WidgetCollection.extend({
    url: Ctx.getApiV2DiscussionUrl("/active_widgets"),
}) {}

/**
 * A subset of the widgets relevant to a widget context
 * @class app.models.widget.WidgetSubset
 */
class WidgetSubset extends Backbone.Subset {
    beforeInitialize(models, options) {
        this.context = options.context;
        this.idea = options.idea;
        this.liveupdate_keys = options.liveupdate_keys;
    }

    sieve(widget) {
        return widget.isRelevantFor(this.context, this.idea);
    }

    comparator(widget) {
        return widget.get("end_date");
    }
}

export default {
    Model: WidgetModel,
    Collection: WidgetCollection,
    WidgetSubset: WidgetSubset,
    localWidgetClassCollection: localWidgetClassCollection,
    globalWidgetClassCollection: globalWidgetClassCollection,
    ActiveWidgetCollection: ActiveWidgetCollection,
    TokenVoteSpecificationModel: TokenVoteSpecificationModel,
    TokenIdeaVoteModel: TokenIdeaVoteModel,
    TokenIdeaVoteCollection: TokenIdeaVoteCollection,
    TokenCategorySpecificationModel: TokenCategorySpecificationModel,
    TokenCategorySpecificationCollection: TokenCategorySpecificationCollection,
    VoteResultCollection: VoteResultCollection,
};
