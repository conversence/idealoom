/**
 * The link between an idea and a message.
 * @module app.models.ideaContentLink
 */
import Marionette from 'backbone.marionette';
import Backbone from 'backbone';
import _ from 'underscore';
import $ from 'jquery';
import Promise from 'bluebird';
import Moment from 'moment';

import i18n from '../utils/i18n.js';
import Types from '../utils/types.js';
import Base from './base.js';
import Ctx from '../common/context.js';
/**
 * @function app.models.ideaContentLink.IdeaContentLinkTypeRank
 */
var IdeaContentLinkTypeRank = function() {
    var IDEA_RELATED_POST_LINK = Types.IDEA_RELATED_POST_LINK;
    var EXTRACT = Types.EXTRACT;
    this._ranks = {};
    this._ranks[IDEA_RELATED_POST_LINK] = 0;
    this._ranks[EXTRACT] = 1;
};
IdeaContentLinkTypeRank.prototype = {
    getRank: function(t){
        if (this._ranks[t]) {
            return this._ranks[t];
        }
        else {
            return null;
        }
    }
};

/**
 * Idea content link model
 * Frontend model for :py:class:`assembl.models.idea_content_link.IdeaContentLink`
 * @class app.models.ideaContentLink.IdeaContentLinkModel
 * @extends app.models.base.BaseModel
 */
class IdeaContentLinkModel extends Base.Model.extend({
    /**
     * @member {string} app.models.ideaContentLink.IdeaContentLinkModel.urlRoot
     */
    urlRoot: Ctx.getApiV2Url(Types.IDEA_CONTENT_LINK),

    /**
     * Defaults
     * @type {Object}
     */
    defaults: {
        idIdea: null,
        idPost: null,
        idCreator: null,
        idExcerpt: null,
    }
}) {
    /**
     * Returns the post creator model promise
     * @returns {Promise}
     * @function app.models.ideaContentLink.IdeaContentLinkModel.getPostCreatorModelPromise
     */
    getPostCreatorModelPromise() {
        var that = this;
        var messageId = this.get('idPost');
        return this.collection.collectionManager.getMessageFullModelPromise(messageId)
            .then(function(messageModel){
                var postCreatorId = messageModel.get('idCreator');
                return Promise.join(postCreatorId, that.collection.collectionManager.getAllUsersCollectionPromise(),
                    function(postCreatorId, users) {
                        var u = users.get(postCreatorId);
                        if (!u){
                            throw new Error("[ideaContentLink] user with id " + that.get('idCreator') + " was not found");
                        }
                        return Promise.resolve(u);
                    }); 
            });
    }

    /**
     * Returns the link creator model promise
     * @returns {Promise}
     * @function app.models.ideaContentLink.IdeaContentLinkModel.getLinkCreatorModelPromise
     */
    getLinkCreatorModelPromise() {
        var that = this;
        return this.collection.collectionManager.getAllUsersCollectionPromise()
            .then(function(users){
                var u = users.get(that.get('idCreator'));
                if (!u) {
                    throw new Error("[ideaContentLink] user with id " + that.get('idCreator') + " was not found");
                }
                return Promise.resolve(u);
            })
            .error(function(e){
                console.error(e.statusText);
            });
    }

    /**
     * Returns message structure model promise
     * @returns {Promise}
     * @function app.models.ideaContentLink.IdeaContentLinkModel.getMessageStructurePromise
     */
    getMessageStructurePromise() {
        var that = this;
        return this.collection.collectionManager.getAllMessageStructureCollectionPromise()
            .then(function(messages){
                var m = messages.find(function(message){
                    return message.id === that.get('idPost');
                });
                if (!m) {
                    throw new Error("[ideaContentLink] message with id " + that.get('idPost') + " was not found");
                }
                return Promise.resolve(m);
            })
            .error(function(e){
                console.error(e.statusText);
            });
    }

    /**
     * Returns idea model promise
     * @returns {Promise}
     * @function app.models.ideaContentLink.IdeaContentLinkModel.getMessageStructurePromise
     */
    getIdeaModelPromise() {
        var that = this;
        return this.collection.collectionManager.getAllIdeasCollectionPromise()
            .then(function(ideas){
                var i = ideas.find(function(idea){
                    return idea.id === that.get('idIdea');
                });

                if (!i) {
                    throw new Error("[ideaContentLink] idea with id " + that.get('idIdea') + " was not found");
                }

                return Promise.resolve(i);
            })
            .error(function(e){
                console.error(e.statusText);
            });
    }

    /**
     * Helper function for the comparator, might not work
     * @returns {Boolean}
     * @function app.models.ideaContentLink.IdeaContentLinkModel.isDirect
     */
    isDirect() {
        return this.get('idPost') === this.collection.messageModel.id;
    }

    /**
     * @returns {String}
     * @function app.models.ideaContentLink.IdeaContentLinkModel.getCreationDate
     */
    getCreationDate() {
        return this.get('created');
    }
}

/**
 * Idea content link collection
 * This Collection is NOT created from an API call, like most other models, collections.
 * It will be created from an array that will be passed from the message model.
 * @class app.models.ideaContentLink.Collection
 * @extends app.models.base.BaseCollection
 */
class Collection extends Base.Collection.extend({
    /**
     * @member {string} app.models.ideaContentLink.Collection.url
     */
    url: Ctx.getApiV2DiscussionUrl('idea_content_links'),

    /**
     * The model
     * @type {IdeaContentLinkModel}
     */
    model: IdeaContentLinkModel
}) {
    /**
     * @member {string} app.models.ideaContentLink.Collection.initialize
     */
    initialize(attrs, options) {
        const _options = options || {};
        this.messageModel = _options.message || {};
        this.url = _options.url || Object.getPrototypeOf(this).url;
        Base.Collection.prototype.initialize.call(this, attrs, options);
    }

    /**
     * Firstly, sort based on direct vs indirect, then sort based on types. If the types match, sort in ascending order.
     * @param {Object} one
     * @param {Object} two
     * @function app.models.ideaContentLink.Collection.comparator
     */
    comparator(one, two) {
        function sortByDate(one, two){
            var d1 = Moment(one.getCreationDate());
            var d2 = Moment(one.getCreationDate());

            if (d1.isBefore(d2)) {return -1;}
            if (d2.isBefore(d1)) {return 1;}
            else {return 0;}
        }
        function sortByType(one, two){
            var t1 = one.get('@type');
            var t2 = two.get('@type');
            var ranker = new IdeaContentLinkTypeRank();
            var rank1 = ranker.getRank(t1);
            var rank2 = ranker.getRank(t2);

            if (rank1 < rank2) { return -1; }
            if (rank2 < rank1) { return 1; }
            else {
                return sortByDate(one, two);
            }
        }
        var isDirect1 = one.isDirect();
        var isDirect2 = two.isDirect();
        if (isDirect1 && !isDirect2) { return -1;}
        if (!isDirect1 && isDirect2) { return 1; }
        else {
            return sortByType(one, two);
        }
    }

    /**
     * The string of short names of the ideas that a message is associated to. Note: It does not contain those that the user clipboarded.
     * @returns {Array}
     * @function app.models.ideaContentLink.Collection.getIdeaNamesPromise
     */
    getIdeaNamesPromise() {
        var that = this;
        return Promise.join(
            this.collectionManager.getAllIdeasCollectionPromise(),
            this.collectionManager.getUserLanguagePreferencesPromise(Ctx),
            function(ideas, userPrefs) {
                var usableIdeaContentLinks = that.filter(function(icl) {
                    if (icl){
                        return icl.get('idIdea') !== null;
                    }
                    else {
                        return false;
                    }
                });
                var m = _.map(usableIdeaContentLinks, function(ideaContentLink) {
                    var idIdea = ideaContentLink.get('idIdea');
                    var ideaModel = ideas.get(idIdea);
                    if (!ideaModel){
                      return i18n.gettext("(hidden idea)");
                    }
                    return ideaModel.getShortTitleDisplayText(userPrefs);
                });
                //A cache of the name, and sort order of the name of the idea
                var cache = {};
                _.each(m, function(name, index, collection){
                    if (!_.has(cache, name)){
                        cache[name] = index;
                    }
                });
                var sorted = _.chain(cache)
                              .pairs()
                              .sortBy(function(val){return val[1]; })
                              .map(function(val){return val[0]; })
                              .value();
                return Promise.resolve(sorted);
            })
            .error(function(e){
                console.error("[IdeaContentLink] Error in getting idea names: ", e.statusText);
            });
    }
}

export default {
    Model: IdeaContentLinkModel,
    Collection: Collection
}    
