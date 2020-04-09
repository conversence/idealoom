/**
 *
 * @module app.views.postFilters
 */

import Ctx from "../common/context.js";

import i18n from "../utils/i18n.js";
import CollectionManager from "../common/collectionManager.js";
import Promise from "bluebird";

var collectionManager = new CollectionManager();

/** Base interface of all filters */
class AbstractFilter {
    constructor() {
        this._values = [];
    }

    /**
     * @returns true if a value was actually added to the filter, false otherwise
     * (tried to add a duplicate value)
     */
    addValue(value) {
        if (!this.isValueInFilter(value)) {
            var index = _.sortedIndex(this._values, value);
            this._values.splice(index, 0, value);

            //console.log("AbstractFilter.addValue added value", value, "value are now:", this._values);
            return true;
        } else {
            return false;
        }
    }

    /**
     * @returns true if a value was actually deleted from the filter, false otherwise
     * (tried to add a duplicate value)
     */
    deleteValue(value) {
        //console.log("deleteValue called with",value, "on values", this._values);
        var indexOfValue = _.indexOf(this._values, value, true);
        console.log(indexOfValue);

        if (indexOfValue !== -1) {
            this._values.splice(indexOfValue, 1);

            //console.log("deleteValue cleared something, values is now", this._values);
            return true;
        } else {
            return false;
        }
    }

    /**
     * @returns true if a value was actually deleted from the filter, false otherwise
     * (tried to add a duplicate value)
     */
    deleteValueAtIndex(valueIndex) {
        //console.log("deleteValueAtIndex called with",valueIndex, "on values", this._values);

        if (valueIndex !== -1 && valueIndex !== null) {
            this._values.splice(valueIndex, 1);

            //console.log("deleteValueAtIndex cleared something, values is now", this._values);
            return true;
        } else {
            return false;
        }
    }

    getValues() {
        return this._values;
    }

    isValueInFilter(value) {
        //console.log("isValueInFilter called with", value, ", ", this._values,"returning", _.contains(this._values, value));
        return _.contains(this._values, value);
    }

    /** Used for CSS ids, and finding filters in queries */
    getId() {
        throw new Error("Need to implement getId");
    }

    /** Generates a unique CSS class for a button to add the filter */
    getAddButtonCssClass() {
        return "js_filter-" + this.getId() + "-add-button";
    }

    getLabelPromise() {
        throw new Error("Need to implement getLabelPromise");
    }

    /** This is the text used for hover help
     * @returns The help text, or null if none is available */
    getHelpText() {
        return null;
    }

    /** Get the name of the GET parameter on the server to put the value in
     * @returns string */
    getServerParam() {
        throw new Error("Need to implement getServerParam");
    }

    getFilterIndividualValueDescriptionStringPromise(individualFilterValue) {
        var retval;
        retval = individualFilterValue;
        return Promise.resolve(individualFilterValue);
    }

    getFilterDescriptionStringPromise(individualValuesButtonsPromises) {
        return Promise.all(individualValuesButtonsPromises).then(
            (individualValuesButtons) => {
                return this.getLabelPromise().then((label) => {
                    return i18n.sprintf(
                        i18n.ngettext(
                            "%s (%s)",
                            "%s (%s)",
                            _.size(individualValuesButtons)
                        ),
                        label,
                        individualValuesButtons.join(", ")
                    );
                });
            }
        );
    }

    /** Get a client side implementation of the filter, if it has one.
     * A client side implementation allows filtering on the client side if it's
     * faster */
    getClientSideImplementation() {
        throw new Error("RESERVED FOR FUTURE USE");
    }

    getIncompatibleFiltersIds() {
        return [];
    }
}

/** For filters who can only have a single value */
class AbstractFilterSingleValue extends AbstractFilter {
    /** For filters who can only have a single, implicit value
     * Typically displayed in the filters menu */
    getImplicitValuePromise() {
        return undefined;
    }

    addValue(value) {
        if (!this.isValueInFilter(value)) {
            if (_.size(this._values) !== 0) {
                throw new Error(
                    "Filter can only have a single value, and we were provided" +
                        value
                );
            }
        }

        return AbstractFilter.prototype.addValue.call(this, value);
    }
}

/** For filters who can only have a single, true or false */
class AbstractFilterBooleanValue extends AbstractFilterSingleValue {
    addValue(value) {
        //console.log("AbstractFilterBooleanValue::addValue called with", value)
        if (!this.isValueInFilter(value)) {
            if (!(value === true || value === false)) {
                console.log(value);
                throw new Error(
                    "Filter expects a boolean value, and we were provided with: " +
                        value
                );
            }
        }

        return AbstractFilterSingleValue.prototype.addValue.call(this, value);
    }

    getFilterIndividualValueDescriptionStringPromise(individualFilterValue) {
        return this.getLabelPromise().then((label) => {
            var retval = i18n.sprintf(
                individualFilterValue === true
                    ? i18n.gettext("%s")
                    : i18n.gettext("NOT %s"),
                label
            );
            return retval;
        });
    }
}

class FilterPostHasIdIn extends AbstractFilter {
    getId() {
        return "post_has_id_in";
    }
    getServerParam() {
        return "ids";
    }
    getLabelPromise() {
        return Promise.resolve(i18n.gettext("Posts with specific ids"));
    }

    getHelpText() {
        return i18n.gettext(
            "Only include posts that are in a range of specific ids"
        );
    }
}

class FilterPostIsInContextOfIdea extends AbstractFilterSingleValue {
    getId() {
        return "post_in_context_of_idea";
    }
    getServerParam() {
        return "root_idea_id";
    }
    getLabelPromise() {
        return Promise.resolve(i18n.gettext("Related to idea"));
    }
    getHelpText() {
        return i18n.gettext(
            "Only include messages related to the specified idea.  The filter is recursive:  Messages related to ideas that are descendents of the idea are included."
        );
    }

    getFilterIndividualValueDescriptionStringPromise(individualFilterValue) {
        return Promise.join(
            collectionManager.getAllIdeasCollectionPromise(),
            collectionManager.getUserLanguagePreferencesPromise(Ctx),
            (allIdeasCollection, translationData) => {
                var idea = allIdeasCollection.get(individualFilterValue);
                if (!idea) {
                    throw new Error(
                        "Idea " + individualFilterValue + " not found"
                    );
                }

                return '"' + idea.getShortTitleSafe(translationData) + '"';
            }
        );
    }
    getFilterDescriptionStringPromise(individualValuesButtonsPromises) {
        return Promise.all(individualValuesButtonsPromises).then(
            (individualValuesButtons) => {
                return i18n.sprintf(
                    i18n.ngettext(
                        "Discuss idea %s",
                        "Discuss ideas: %s",
                        individualValuesButtons.length
                    ),
                    individualValuesButtons.join(i18n.gettext(" AND "))
                );
            }
        );
    }
}

class FilterPostIsDescendentOfPost extends AbstractFilterSingleValue {
    getId() {
        return "post_thread";
    }
    getServerParam() {
        return "root_post_id";
    }
    getLabelPromise() {
        return Promise.resolve(i18n.gettext("Part of thread of"));
    }
    getHelpText() {
        return i18n.gettext(
            "Only include messages that are in the specified post reply thread."
        );
    }
    getFilterIndividualValueDescriptionStringPromise(individualFilterValue) {
        return Promise.join(
            collectionManager.getMessageFullModelPromise(individualFilterValue),
            collectionManager.getUserLanguagePreferencesPromise(Ctx),
            (post, ulp) => {
                if (!post) {
                    throw new Error(
                        "Post " + individualFilterValue + " not found"
                    );
                }
                var subject = post.get("subject");
                var subjectText = subject
                    ? subject.bestValue(ulp.getTranslationData())
                    : "";

                if (post.get("@type") === "SynthesisPost") {
                    return i18n.sprintf(
                        i18n.gettext('synthesis "%s"'),
                        subjectText
                    );
                } else {
                    return i18n.sprintf(
                        i18n.gettext('message "%s"'),
                        subjectText
                    );
                }
            }
        );
    }
    getFilterDescriptionStringPromise(individualValuesButtonsPromises) {
        return Promise.all(individualValuesButtonsPromises).then(
            (individualValuesButtons) => {
                return i18n.sprintf(
                    i18n.gettext("Are in the conversation that follows: %s"),
                    individualValuesButtons.join(i18n.gettext(" AND "))
                );
            }
        );
    }
}

class FilterPostIsDescendentOrAncestorOfPost extends AbstractFilterSingleValue {
    getId() {
        return "post_ancestry_and_thread";
    }
    getServerParam() {
        return "family_post_id";
    }
    getLabelPromise() {
        return Promise.resolve(i18n.gettext("Part of the context of"));
    }
    getHelpText() {
        return i18n.gettext(
            "Only include messages that are in the specified post reply thread or ancestry."
        );
    }
    getFilterIndividualValueDescriptionStringPromise(individualFilterValue) {
        return Promise.join(
            collectionManager.getMessageFullModelPromise(individualFilterValue),
            collectionManager.getUserLanguagePreferencesPromise(Ctx),
            (post, ulp) => {
                if (!post) {
                    throw new Error(
                        "Post " + individualFilterValue + " not found"
                    );
                }
                var subject = post.get("subject");
                var subjectText = subject
                    ? subject.bestValue(ulp.getTranslationData())
                    : "";

                if (post.get("@type") === "SynthesisPost") {
                    return i18n.sprintf(
                        i18n.gettext('synthesis "%s"'),
                        subjectText
                    );
                } else {
                    return i18n.sprintf(
                        i18n.gettext('message "%s"'),
                        subjectText
                    );
                }
            }
        );
    }
    getFilterDescriptionStringPromise(individualValuesButtonsPromises) {
        return Promise.all(individualValuesButtonsPromises).then(
            (individualValuesButtons) => {
                return i18n.sprintf(
                    i18n.gettext("Are in the context of: %s"),
                    individualValuesButtons.join(i18n.gettext(" AND "))
                );
            }
        );
    }
}

class FilterPostIsFromUser extends AbstractFilterSingleValue {
    getId() {
        return "post_is_from";
    }
    getServerParam() {
        return "post_author";
    }
    getLabelPromise() {
        return Promise.resolve(i18n.gettext("Posted by"));
    }
    getHelpText() {
        return i18n.gettext(
            "Only include messages that are posted by a specific user."
        );
    }
    getFilterIndividualValueDescriptionStringPromise(individualFilterValue) {
        return collectionManager
            .getAllUsersCollectionPromise(individualFilterValue)
            .then((users) => {
                var user = users.get(individualFilterValue);
                if (!user) {
                    throw new Error(
                        "User " + individualFilterValue + " not found"
                    );
                }

                return i18n.sprintf(i18n.gettext('"%s"'), user.get("name"));
            });
    }
    getFilterDescriptionStringPromise(individualValuesButtonsPromises) {
        return Promise.all(individualValuesButtonsPromises).then(
            (individualValuesButtons) => {
                return i18n.sprintf(
                    i18n.gettext("Are posted by: %s"),
                    individualValuesButtons.join(i18n.gettext(" AND "))
                );
            }
        );
    }
}

class FilterPostIsOwnPost extends FilterPostIsFromUser {
    getId() {
        return "only_own_posts";
    }
    getImplicitValuePromise() {
        return Promise.resolve(Ctx.getCurrentUser().id);
    }
    getLabelPromise() {
        return Promise.resolve(i18n.gettext("Messages I posted"));
    }
    getHelpText() {
        return i18n.gettext("Only include messages that I posted.");
    }
}

class FilterPostReplyToUser extends AbstractFilterSingleValue {
    getId() {
        return "post_replies_to_user";
    }
    getServerParam() {
        return "post_replies_to";
    }
    getLabelPromise() {
        return Promise.resolve(i18n.gettext("Replies to"));
    }
    getHelpText() {
        return i18n.gettext(
            "Only include messages that reply to a specific user."
        );
    }
    getFilterIndividualValueDescriptionStringPromise(individualFilterValue) {
        return collectionManager
            .getAllUsersCollectionPromise(individualFilterValue)
            .then((users) => {
                var user = users.get(individualFilterValue);
                if (!user) {
                    throw new Error(
                        "User " + individualFilterValue + " not found"
                    );
                }

                return i18n.sprintf(i18n.gettext('"%s"'), user.get("name"));
            });
    }
    getFilterDescriptionStringPromise(individualValuesButtonsPromises) {
        return Promise.all(individualValuesButtonsPromises).then(
            (individualValuesButtons) => {
                return i18n.sprintf(
                    i18n.gettext("Replies to: %s"),
                    individualValuesButtons.join(i18n.gettext(" AND "))
                );
            }
        );
    }
}

class FilterPostReplyToMe extends FilterPostReplyToUser {
    getId() {
        return "post_replies_to_me";
    }
    getImplicitValuePromise() {
        return Promise.resolve(Ctx.getCurrentUser().id);
    }
    getLabelPromise() {
        return Promise.resolve(i18n.gettext("Messages that reply to me"));
    }
    getHelpText() {
        return i18n.gettext(
            "Only include messages that reply one of the messages I posted."
        );
    }
}

class FilterPostIsOrphan extends AbstractFilterBooleanValue {
    getId() {
        return "only_orphan_posts";
    }
    getImplicitValuePromise() {
        return Promise.resolve(true);
    }
    getServerParam() {
        return "only_orphan";
    }
    getLabelPromise() {
        return Promise.resolve(
            i18n.gettext("Messages not yet associated with an idea")
        );
    }
    getHelpText() {
        return i18n.gettext(
            "Only include messages that are not found in any idea."
        );
    }
}

class FilterPostNotHarvested extends AbstractFilterBooleanValue {
    getId() {
        return "not_harvested";
    }
    getImplicitValuePromise() {
        return Promise.resolve(true);
    }
    getServerParam() {
        return "not_harvested";
    }
    getLabelPromise() {
        return Promise.resolve(
            i18n.gettext("Messages that were not harvested")
        );
    }
    getHelpText() {
        return i18n.gettext("Only include messages that were not harvested.");
    }
}

class FilterPostIsSynthesis extends AbstractFilterBooleanValue {
    getId() {
        return "only_synthesis_posts";
    }
    getImplicitValuePromise() {
        return Promise.resolve(true);
    }
    getServerParam() {
        return "only_synthesis";
    }
    getLabelPromise() {
        return Promise.resolve(i18n.gettext("Synthesis messages"));
    }
    getHelpText() {
        return i18n.gettext(
            "Only include messages that represent a synthesis of the discussion."
        );
    }
    getFilterDescriptionStringPromise(individualValuesButtonsPromises) {
        return Promise.all(
            individualValuesButtonsPromises,
            this.getLabelPromise()
        ).then((individualValuesButtons, label) => {
            return i18n.sprintf(
                "%s %s",
                label,
                individualValuesButtons.join("")
            );
        });
    }
}

class FilterPostHasUnread extends AbstractFilterBooleanValue {
    getId() {
        return "post_has_unread";
    }
    getServerParam() {
        return "is_unread";
    }
    getLabelPromise() {
        return Promise.resolve(i18n.gettext("Have unread value"));
    }

    getFilterIndividualValueDescriptionStringPromise(individualFilterValue) {
        var retval;
        if (individualFilterValue === true) {
            retval = i18n.gettext("You haven't read yet");
        } else if (individualFilterValue === false) {
            retval = i18n.gettext("You've already read");
        } else {
            throw new Error("Value is not a boolean!");
        }

        return Promise.resolve(retval);
    }
    getFilterDescriptionStringPromise(individualValuesButtonsPromises) {
        return Promise.all(individualValuesButtonsPromises).then(
            (individualValuesButtons) => {
                return i18n.sprintf("%s", individualValuesButtons.join(""));
            }
        );
    }
}

class FilterPostIsUnread extends FilterPostHasUnread {
    getId() {
        return "is_unread_post";
    }
    getImplicitValuePromise() {
        return Promise.resolve(true);
    }
    getLabelPromise() {
        return Promise.resolve(i18n.gettext("Unread messages"));
    }
    getHelpText() {
        return i18n.gettext(
            "Only include messages you haven't read yet, or you manually marked unread."
        );
    }
    getIncompatibleFiltersIds() {
        return ["is_read_post"];
    }
}

class FilterPostIsRead extends FilterPostHasUnread {
    getId() {
        return "is_read_post";
    }
    getImplicitValuePromise() {
        return Promise.resolve(false);
    }
    getLabelPromise() {
        return Promise.resolve(i18n.gettext("Read messages"));
    }
    getHelpText() {
        return i18n.gettext(
            "Only include messages that have previously been marked read."
        );
    }
    getIncompatibleFiltersIds() {
        return ["is_unread_post"];
    }
}

class FilterPostHasText extends AbstractFilterSingleValue {
    constructor() {
        super();
        this.keyword_value = null;
    }
    getId() {
        return "has_text";
    }
    getImplicitValuePromise() {
        return Promise.resolve(this.keyword_value);
    }
    getServerParam() {
        return "keyword";
    }
    getLabelPromise() {
        return this.getImplicitValuePromise().then((value) => {
            return i18n.gettext("Messages with text...");
        });
    }
    getHelpText() {
        return i18n.gettext("Only include posts containing certain keywords.");
    }
    askForValue() {
        var val = window.prompt(i18n.gettext("Search for keywords"));
        if (val) {
            this.keyword_value = val;
        }
        return val;
    }
}
FilterPostHasText.should_ask_value_from_user = true;

class FilterPostIsPostedAfterDate extends AbstractFilterSingleValue {
    constructor() {
        super();
        this.date_value = null;
    }
    getId() {
        return "is_posted_after_date";
    }
    getImplicitValuePromise() {
        return Promise.resolve(this.date_value);
    }
    getServerParam() {
        return "posted_after_date";
    }
    setDate(date) {
        // we want to set something like "2015-04-11T01%3A59%3A23Z"
        var processInputDate = (d) => {
            var d2 = new Date(d);
            return d2.toISOString();
        };
        this.date = processInputDate(date);
        this.date_value = date;
    }
    getLabelPromise() {
        return this.getImplicitValuePromise().then((value) => {
            // commented because the label of the filter in filter menu is the same as the label of the tag when the filter is active
            //if ( value === null ){
            return i18n.gettext("Messages posted after...");
            //}
            //return i18n.sprintf(i18n.gettext('Messages posted after %s'), Ctx.getNiceDateTime(value));
        });
    }
    getHelpText() {
        return i18n.gettext("Only include posts created after a given date.");
    }
    askForValue() {
        var defaultValue = this.date_value ? this.date_value : "2015-01-01";
        var val = window.prompt(
            i18n.gettext(
                "Please type a date. The filter will then show only posts which have been created after this date. Example: 2015-01-01"
            ),
            defaultValue
        );
        if (val) {
            this.setDate(val);
        }
        return val;
    }
}
FilterPostIsPostedAfterDate.should_ask_value_from_user = true;

class FilterPostIsPostedBeforeDate extends AbstractFilterSingleValue {
    constructor() {
        super();
        this.date_value = null;
        this.should_ask_value_from_user = true;
    }
    getId() {
        return "is_posted_before_date";
    }
    getImplicitValuePromise() {
        return Promise.resolve(this.date_value);
    }
    getServerParam() {
        return "posted_before_date";
    }
    getLabelPromise() {
        return this.getImplicitValuePromise().then((value) => {
            // commented because the label of the filter in filter menu is the same as the label of the tag when the filter is active
            //if ( value === null ){
            return i18n.gettext("Messages posted before...");
            //}
            //return i18n.sprintf(i18n.gettext('Messages posted before %s'), Ctx.getNiceDateTime(value));
        });
    }
    setDate(date) {
        // we want to set something like "2015-04-11T01%3A59%3A23Z"
        var processInputDate = (d) => {
            var d2 = new Date(d);
            return d2.toISOString();
        };
        this.date = processInputDate(date);
        this.date_value = date;
    }
    getHelpText() {
        return i18n.gettext("Only include posts created before a given date.");
    }
    askForValue() {
        var defaultValue = this.date_value ? this.date_value : "2015-01-01";
        var val = window.prompt(
            i18n.gettext(
                "Please type a date. The filter will then show only posts which have been created before this date. Example: 2015-01-01"
            ),
            defaultValue
        );
        if (val) {
            this.setDate(val);
        }
        return val;
    }
}
FilterPostIsPostedBeforeDate.should_ask_value_from_user = true;

class FilterPostIsPostedSinceLastSynthesis extends AbstractFilterSingleValue {
    getId() {
        return "is_posted_since_last_synthesis";
    }
    getImplicitValuePromise() {
        var that = this;
        var collectionManager = new CollectionManager();

        return collectionManager
            .getAllMessageStructureCollectionPromise()
            .then((allMessageStructureCollection) => {
                var date = null;
                var lastSynthesisPost = allMessageStructureCollection.getLastSynthesisPost();
                if (lastSynthesisPost) {
                    return lastSynthesisPost.get("date");
                } else {
                    return undefined;
                }
            });
    }
    getServerParam() {
        return "posted_after_date";
    }
    getLabelPromise() {
        return this.getImplicitValuePromise().then((value) => {
            return i18n.sprintf(
                i18n.gettext("Messages posted since the last synthesis (%s)"),
                Ctx.getNiceDateTime(value)
            );
        });
    }
    getHelpText() {
        return i18n.gettext(
            "Only include posts created after the last synthesis."
        );
    }
}

class FilterPostIsDeleted extends AbstractFilterSingleValue {
    getId() {
        return "only_deleted_posts";
    }
    getImplicitValuePromise() {
        return Promise.resolve("true");
    }
    getServerParam() {
        return "deleted";
    }
    getLabelPromise() {
        return Promise.resolve(i18n.gettext("Deleted messages"));
    }
    getHelpText() {
        return i18n.gettext(
            "Only include messages that have been deleted (by their author or by an administrator), and their ancestors."
        );
    }
    getFilterIndividualValueDescriptionStringPromise(individualFilterValue) {
        return Promise.resolve("");
    }
    getFilterDescriptionStringPromise(individualValuesButtonsPromises) {
        var that = this;
        return Promise.all(individualValuesButtonsPromises).then(
            (individualValuesButtons) => {
                return that.getLabelPromise().then((label) => {
                    return label + individualValuesButtons.join("");
                });
            }
        );
    }
    getIncompatibleFiltersIds() {
        return ["also_deleted_posts"];
    }
}

class FilterPostIsDeletedOrNot extends AbstractFilterSingleValue {
    getId() {
        return "also_deleted_posts";
    }
    getImplicitValuePromise() {
        return Promise.resolve("any");
    }
    getServerParam() {
        return "deleted";
    }
    getLabelPromise() {
        return Promise.resolve(i18n.gettext("Show also deleted messages"));
    }
    getHelpText() {
        return i18n.gettext(
            "Also include messages that have been deleted (by their author or by an administrator)."
        );
    }
    getFilterIndividualValueDescriptionStringPromise(individualFilterValue) {
        return Promise.resolve("");
    }
    getFilterDescriptionStringPromise(individualValuesButtonsPromises) {
        var that = this;
        return Promise.all(individualValuesButtonsPromises).then(
            (individualValuesButtons) => {
                return that.getLabelPromise().then((label) => {
                    return label + individualValuesButtons.join("");
                });
            }
        );
    }
    getIncompatibleFiltersIds() {
        return ["only_deleted_posts"];
    }
}

var availableFilters = {
    POST_HAS_ID_IN: FilterPostHasIdIn,
    POST_IS_IN_CONTEXT_OF_IDEA: FilterPostIsInContextOfIdea,
    POST_IS_DESCENDENT_OF_POST: FilterPostIsDescendentOfPost,
    POST_IS_DESCENDENT_OR_ANCESTOR_OF_POST: FilterPostIsDescendentOrAncestorOfPost,
    POST_IS_ORPHAN: FilterPostIsOrphan,
    POST_NOT_HARVESTED: FilterPostNotHarvested,
    POST_IS_SYNTHESIS: FilterPostIsSynthesis,
    POST_HAS_TEXT: FilterPostHasText,
    POST_IS_UNREAD: FilterPostIsUnread,
    POST_IS_READ: FilterPostIsRead,
    POST_IS_POSTED_SINCE_LAST_SYNTHESIS: FilterPostIsPostedSinceLastSynthesis,
    POST_IS_POSTED_AFTER_DATE: FilterPostIsPostedAfterDate,
    POST_IS_POSTED_BEFORE_DATE: FilterPostIsPostedBeforeDate,
    POST_IS_FROM: FilterPostIsFromUser,
    POST_IS_FROM_SELF: FilterPostIsOwnPost,
    POST_REPONDS_TO: FilterPostReplyToUser,
    POST_REPONDS_TO_ME: FilterPostReplyToMe,
    POST_IS_DELETED: FilterPostIsDeleted,
    POST_IS_DELETED_OR_NOT: FilterPostIsDeletedOrNot,
};

export default availableFilters;
