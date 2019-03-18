/**
 * A segment of text extracted from a message. Can be associated to an idea, otherwise in clipboard.
 * @module app.models.segment
 */

import _ from 'underscore';

import Base from './base.js';
import Promise from 'bluebird';
import Ctx from '../common/context.js';
import Agents from './agents.js';
import AnnotatorF from 'annotator/annotator-full.js';
import Message from './message.js';
import Types from '../utils/types.js';
import i18n from '../utils/i18n.js';

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
    text: '',
    quote: '',
    idPost: null,
    idIdea: null,
    created: null,
    idCreator: null,
    important: false,
    ranges: [],
    target: null
  }
}) {
  /**
   * @init
   */
  initialize() {
    if (this.attributes.created) {
      this.attributes.created = this.attributes.created;
    }

    if (!this.get('created')) {
      this.set('created', Ctx.getCurrentTime());
    }

    var ranges = this.attributes.ranges;
    var _serializedRange = [];
    var _ranges = [];

    _.each(ranges, function(range, index) {

      if (!(range instanceof Annotator.Range.SerializedRange)) {
        ranges[index] = new Annotator.Range.SerializedRange(range);
      }

      _ranges[index] = ranges[index];

    });

    // We need to create a copy 'cause annotator destroy all ranges
    // once it creates the highlight
    this.attributes._ranges = _ranges;
    var that = this;

    this.listenTo(this, "change:idIdea", function() {
      that.collection.collectionManager.getAllIdeasCollectionPromise()
                .done(function(allIdeasCollection) {
        var previousIdea;
        var idea;

        if (that.previous("idIdea") !== null) {
          previousIdea = allIdeasCollection.get(that.previous("idIdea"));

          //console.log("Segment:initialize:triggering idea change (previous idea)");
          previousIdea.trigger('change');
        }

        if (that.get('idIdea') !== null) {

          idea = allIdeasCollection.get(that.get('idIdea'));

          //console.log("Segment:initialize:triggering idea change (new idea)");
          idea.trigger('change');
        }
      });
    })

    // cleaning
    delete this.attributes.highlights;
  }

  /**
   * Validation
   */
  validate(attrs, options) {
    var currentUser = Ctx.getCurrentUser();
    var id = currentUser.getId();

    if (!id) {
      return i18n.gettext('You must be logged in to create segments');
    }

    /*
     * Extracts CAN have a null idPost: it is the case for extracts harvested from a distant webpage.
     * But if the extract has no idPost field, then it must have an uri field.
    if (attrs.idPost === null || typeof attrs.idPost !== 'string') {
        return i18n.gettext('invalid idPost: ' + attrs.idPost);
    }
    */
    if ((attrs.idPost === null || typeof attrs.idPost !== 'string') && (attrs.uri === null || typeof attrs.uri !== 'string')) {
      return i18n.sprintf(i18n.gettext(
        'invalid extract: the extract must have a valid idPost (here %s) or a valid uri (here %s)'),
        attrs.idPost, attrs.uri);
    }

    if (attrs.created === null) {
      return i18n.gettext('invalid created: ') + attrs.created;
    }

    if (attrs.idIdea !== null && typeof attrs.idIdea !== 'string') {
      return i18n.gettext('invalid idIdea: ') + attrs.idIdea;
    }

    if (attrs.idCreator === null || typeof attrs.idCreator !== 'string') {
      return i18n.gettext('invalid idCreator: ') + attrs.idCreator;
    }
  }

  /** Return a promise for the Post the segments is associated to, if any
   * @returns {$.Defered.Promise}
   */
  getAssociatedIdeaPromise() {
    var that = this;
    var idIdea = this.get('idIdea');
    if (idIdea) {
      return this.collection.collectionManager.getAllIdeasCollectionPromise().then(function(allIdeasCollection) {
        return allIdeasCollection.get(idIdea);
      });
    }
    else {
      return Promise.resolve(null);
    }
  }

  /** Return a promise for the Post the segments is associated to, if any
   * @returns {$.Defered.Promise}
   */
  getAssociatedPostPromise() {
    return this.collection.collectionManager.getMessageFullModelPromise(this.get('idPost'));
  }

  /**
   * Return the html markup to the icon
   * @returns {string}
   */
  getTypeIcon() {
    var cls = 'icon-';
    var target = this.get('target');
    var idPost = this.idPost;

    // todo(Marc-Antonie): review this `type` because `idPost`
    // is a string and doesn't have `@type` attribute

    if (target != null) {
      switch (target['@type']) {
        case 'Webpage':
          cls += 'link';
          break;

        case 'Email':
        case 'Post':
        case 'LocalPost':
        case 'SynthesisPost':
        case 'ImportedPost':
        default:
          cls += 'mail';
      }
    } else if (idPost != null) {
      cls += 'mail';
    }

    return Ctx.format("<i class='{0}'></i>", cls);
  }

  /**
   * Returns the extract's creator from a collection provided
   * @param {Collection} The collection to get the user models from
   * @returns {User}
   */
  getCreatorFromUsersCollection(usersCollection) {
    var creatorId = this.get('idCreator');
    var creator = usersCollection.getById(creatorId);
    if (!creatorId) {
      throw new Error("A segment cannot have an empty creator");
    }

    return creator;
  }

  /**
   * Alias for `.get('quote') || .get('text')`
   * @returns {string}
   */
  getQuote() {
    return this.get('quote') || this.get('text');
  }

  getCreatedTime() {
    if (!this.createdTime) {
      this.createdTime = (new Date(this.get('created'))).getTime();
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
  model: SegmentModel
}) {
  /**
   * @init
   */
  initialize() {

  }

  /**
   * Returns the segment related to the annotation
   * @param  {annotation} annotation
   * @returns {Segment}
   */
  getByAnnotation(annotation) {
    return this.get(annotation['@id']);
  }

  /**
   * Transform an annotator annotation as an extract.
   * The segment isn't saved.
   * @param {annotation} annotation
   * @param {number} [idIdea=null]
   * @returns {Segment}
   */
  addAnnotationAsExtract(annotation, idIdea) {
    var that = this;
    var idPost = Ctx.getPostIdFromAnnotation(annotation);

    //console.log("addAnnotationAsExtract called");

    var segment = new SegmentModel({
      target: { "@id": idPost, "@type": Types.EMAIL },
      text: annotation.text,
      quote: annotation.quote,
      idCreator: Ctx.getCurrentUser().getId(),
      ranges: annotation.ranges,
      idPost: idPost,
      idIdea: idIdea
    });

    if (segment.isValid()) {
      delete segment.attributes.highlights;
      this.add(segment);
    }
    else {
      alert(segment.validationError);
    }

    return segment;
  }
}

export default {
  Model: SegmentModel,
  Collection: SegmentCollection
};

