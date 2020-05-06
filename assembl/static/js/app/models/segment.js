/**
 * A segment of text extracted from a message. Can be associated to an idea, otherwise in clipboard.
 * @module app.models.segment
 */

import _ from "underscore";

import Base from "./base.js";
import Promise from "bluebird";
import Ctx from "../common/context.js";
import Agents from "./agents.js";
import AnnotatorF from "annotator/annotator-full.js";
import Message from "./message.js";
import ideaContentLink from "./ideaContentLink.js";
import Types from "../utils/types.js";
import i18n from "../utils/i18n.js";

const Annotator = AnnotatorF.Annotator;

/**
 * Segment model
 * Frontend model for :py:class:`assembl.models.idea_content_link.Extract`
 * @class app.models.segment.SegmentModel
 * @extends app.models.base.BaseModel
 */

class SegmentModel extends Base.Model.extend({
    /**
     * @type {string}
     */
    urlRoot: Ctx.getApiUrl("extracts"),

    /**
     * @type {Object}
     */
    defaults: {
        text: "",
        quote: "",
        idPost: null,
        ideaLinks: null,
        created: null,
        idCreator: null,
        important: false,
        external_url: null,
        ranges: [],
        target: null,
    },
}) {
    /**
     * @init
     */
    initialize() {
        if (!this.get("created")) {
            this.set("created", Ctx.getCurrentTime());
        }

        if (!this.get("ideaLinks")) {
            this.set(
                "ideaLinks",
                new ideaContentLink.Collection([], {
                    url: this.getIdeaLinkUrl(),
                })
            );
        }

        var ranges = this.attributes.ranges;
        var _serializedRange = [];
        var _ranges = [];

        _.each(ranges, function (range, index) {
            if (!(range instanceof Annotator.Range.SerializedRange)) {
                ranges[index] = new Annotator.Range.SerializedRange(range);
            }

            _ranges[index] = ranges[index];
        });

        // We need to create a copy 'cause annotator destroy all ranges
        // once it creates the highlight
        this.attributes._ranges = _ranges;
        const links = this.get("ideaLinks");
        const updateFn = (icl, coll) => {
            const cm = this.collection
                ? this.collection.collectionManager
                : coll.collectionManager;
            cm.getAllIdeasCollectionPromise().then((allIdeasCollection) => {
                const idea = allIdeasCollection.get(icl.get("idIdea"));
                idea.trigger("change", idea);
                this.trigger("change:ideaLinks", this);
            });
        };
        this.listenTo(links, "remove destroy add change:idIdea", updateFn);
        this.listenTo(this, "change:ideaLinks", (seg, newIL, options) => {
            if (newIL) {
                const oldIL =
                    seg._previousAttributes.ideaLinks || seg.get("ideaLinks");
                if (oldIL != newIL) {
                    this.stopListening(oldIL);
                    this.listenTo(
                        newIL,
                        "remove destroy add change:idIdea",
                        updateFn
                    );
                }
            }
        });

        // cleaning
        delete this.attributes.highlights;
    }

    getIdeaLinkUrl() {
        const id = this.getNumericId();
        if (id)
            return Ctx.getApiV2DiscussionUrl(
                `extracts/${id}/idea_content_links`
            );
        else return Ctx.getApiV2DiscussionUrl("idea_content_links");
    }

    parse(rawModel, options) {
        if (rawModel.ideaLinks) {
            rawModel.ideaLinks = new ideaContentLink.Collection(
                rawModel.ideaLinks,
                { parse: true, url: this.getIdeaLinkUrl() }
            );
        }
        return super.parse(...arguments);
    }

    linkedToIdea(ideaId) {
        const link = this.get("ideaLinks").find(
            (link) => link.get("idIdea") == ideaId
        );
        if (link) {
            link.urlRoot = this.getIdeaLinkUrl();
        }
        return link;
    }

    /**
     * Validation
     */
    validate(attrs, options) {
        var currentUser = Ctx.getCurrentUser();
        var id = currentUser.getId();

        if (!id) {
            return i18n.gettext("You must be logged in to create segments");
        }

        /*
     * Extracts CAN have a null idPost: it is the case for extracts harvested from a distant webpage.
     * But if the extract has no idPost field, then it must have an uri field.
    if (attrs.idPost === null || typeof attrs.idPost !== 'string') {
        return i18n.gettext('invalid idPost: ' + attrs.idPost);
    }
    */
        if (
            (attrs.idPost === null || typeof attrs.idPost !== "string") &&
            (attrs.uri === null || typeof attrs.uri !== "string")
        ) {
            return i18n.sprintf(
                i18n.gettext(
                    "invalid extract: the extract must have a valid idPost (here %s) or a valid uri (here %s)"
                ),
                attrs.idPost,
                attrs.uri
            );
        }

        if (attrs.created === null) {
            return i18n.gettext("invalid created: ") + attrs.created;
        }

        if (attrs.idCreator === null || typeof attrs.idCreator !== "string") {
            return i18n.gettext("invalid idCreator: ") + attrs.idCreator;
        }
    }

    /** Return a promise for the Post the segments is associated to, if any
     * @returns {$.Defered.Promise}
     */
    getAssociatedIdeasPromise() {
        const ideaLinks = this.get("ideaLinks");
        if (ideaLinks) {
            return this.collection.collectionManager
                .getAllIdeasCollectionPromise()
                .then((allIdeasCollection) => {
                    return ideaLinks
                        .map((ideaLink) =>
                            allIdeasCollection.get(ideaLink.get("idIdea"))
                        )
                        .filter((i) => i != undefined);
                });
        } else {
            return Promise.resolve(null);
        }
    }

    getLatestLink() {
        const links = this.get("ideaLinks");
        if (links.length) {
            const byDate = links.sortBy("created");
            return byDate[byDate.length - 1];
        }
    }

    getLatestAssociatedIdeaPromise() {
        const latestLink = this.getLatestLink();
        if (latestLink) {
            return this.collection.collectionManager
                .getAllIdeasCollectionPromise()
                .then((allIdeasCollection) => {
                    return allIdeasCollection.get(latestLink.get("idIdea"));
                });
        } else {
            return Promise.resolve(null);
        }
    }

    /** Return a promise for the Post the segments is associated to, if any
     * @returns {$.Defered.Promise}
     */
    getAssociatedPostPromise() {
        return this.collection.collectionManager.getMessageFullModelPromise(
            this.get("idPost")
        );
    }

    getWebUrl() {
        const target = this.get("target");
        if (target && target["@type"] == "Webpage") {
            return target.url;
        }
    }

    getWebTitle() {
        const target = this.get("target");
        if (target && target["@type"] == "Webpage") {
            return target.title;
        }
    }

    getNumLinkedIdeas() {
        const links = this.get("ideaLinks");
        if (links) {
            return links.models.length;
        }
        return 0;
    }

    addIdeaLink(ideaId) {
        const links = this.get("ideaLinks");
        const link = new ideaContentLink.Model({
            idPost: this.get("idPost"),
            idIdea: ideaId,
            idExcerpt: this.getId(),
            idCreator: this.get("idCreator"),
        });
        link.urlRoot = this.getIdeaLinkUrl();
        links.add(link);
        return link;
    }

    /**
     * Return the html markup to the icon
     * @returns {string}
     */
    getTypeIcon() {
        var cls = "icon-";
        var target = this.get("target");
        var idPost = this.idPost;

        // todo(Marc-Antonie): review this `type` because `idPost`
        // is a string and doesn't have `@type` attribute

        if (target != null) {
            switch (target["@type"]) {
                case "Webpage":
                    cls += "link";
                    break;

                case "Email":
                case "Post":
                case "LocalPost":
                case "SynthesisPost":
                case "ImportedPost":
                default:
                    cls += "mail";
            }
        } else if (idPost != null) {
            cls += "mail";
        }

        return Ctx.format("<i class='{0}'></i>", cls);
    }

    /**
     * Returns the extract's creator from a collection provided
     * @param {Collection} The collection to get the user models from
     * @returns {User}
     */
    getCreatorFromUsersCollection(usersCollection) {
        var creatorId = this.get("idCreator");
        if (!creatorId) {
            throw new Error("A segment cannot have an empty creator");
        }
        var creator = usersCollection.getById(creatorId);
        return creator;
    }

    /**
     * Returns the segment creator model promise
     * @returns {Promise}
     * @function app.models.segment.SegmentModel.getCreatorModelPromise
     */
    getCreatorModelPromise() {
        return this.collection.collectionManager
            .getAllUsersCollectionPromise()
            .then((users) => this.getCreatorFromUsersCollection(users));
    }

    /**
     * Alias for `.get('quote') || .get('text')`
     * @returns {string}
     */
    getQuote() {
        return this.get("quote") || this.get("text");
    }

    getCreatedTime() {
        if (!this.createdTime) {
            this.createdTime = new Date(this.get("created")).getTime();
        }

        return this.createdTime;
    }
}

/**
 * Segment collection
 * @class app.models.segment.SegmentCollection
 * @extends app.models.base.BaseCollection
 */

class SegmentCollection extends Base.Collection.extend({
    /**
     * @type {string}
     */
    url: Ctx.getApiUrl("extracts"),

    /**
     * @type {IdeaModel}
     */
    model: SegmentModel,
}) {
    /**
     * @init
     */
    initialize() {}

    /**
     * Returns the segment related to the annotation
     * @param  {annotation} annotation
     * @returns {Segment}
     */
    getByAnnotation(annotation) {
        return this.get(annotation["@id"]);
    }

    /**
     * Transform an annotator annotation as an extract.
     * The segment isn't saved.
     * @param {annotation} annotation
     * @param {number} [idIdea=null]
     * @returns {Segment}
     */
    addAnnotationAsExtract(annotation, idIdea) {
        const idPost = Ctx.getPostIdFromAnnotation(annotation);
        const idCreator = Ctx.getCurrentUser().getId();

        //console.log("addAnnotationAsExtract called");
        const links = new ideaContentLink.Collection(); // no url yet
        links.collectionManager = this.collectionManager;
        var segment = new SegmentModel({
            target: { "@id": idPost, "@type": Types.EMAIL },
            text: annotation.text,
            quote: annotation.quote,
            idCreator,
            ranges: annotation.ranges,
            idPost: idPost,
            ideaLinks: links,
        });
        if (idIdea) {
            links.add(
                new ideaContentLink.Model({
                    idPost,
                    idIdea,
                    idCreator,
                })
            );
        }

        if (segment.isValid()) {
            delete segment.attributes.highlights;
            this.add(segment);
        } else {
            alert(segment.validationError);
        }

        return segment;
    }

    updateFromSocket(item) {
        if (item["@type"] == Types.EXTRACT) {
            super.updateFromSocket(item);
        } else if (item["@type"] == Types.IDEA_EXTRACT_LINK) {
            const excerptId = item["idExcerpt"];
            // can be null if tombstone
            if (excerptId) {
                const excerpt = this.get(excerptId);
                if (!excerpt) {
                    console.error("where is the excerpt?");
                    return;
                }
                const icl_coll = excerpt.get("ideaLinks");
                icl_coll.updateFromSocket(item);
            }
        }
    }
}

export default {
    Model: SegmentModel,
    Collection: SegmentCollection,
};
