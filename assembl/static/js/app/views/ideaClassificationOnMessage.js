/**
 * 
 * @module app.views.ideaClassificationOnMessage
 */

import Marionette from 'backbone.marionette';

import $ from 'jquery';
import _ from 'underscore';
import Ctx from '../common/context.js';
import CollectionManager from '../common/collectionManager.js';
import Types from '../utils/types.js';
import BreadCrumbView from './breadcrumb.js';
import IdeaModel from '../models/idea.js';
import i18n from '../utils/i18n.js';
import openIdeaInModal from './modals/ideaInModal.js';
import Backbone from 'backbone';
import Promise from 'bluebird';
import LoaderView from './loaderView.js';
import Analytics from '../internal_modules/analytics/dispatcher.js';

// // root class
// var IdeaShowingMessageModel = Backbone.Model.extend({
//   ideaId: null // string. for example "local:Idea/19"
// });


/**
 * Abstract Class of Idea Classification Views
 */
class IdeaClassificationView extends LoaderView.extend({
  template: false,

  ui: {
    viewIdea: ".js_seeIdea",
    breadcrumbs: ".js_breadcrumb"
  },

  events: {
    'click @ui.viewIdea': 'onSeeIdeaClick'
  },

  regions:{
    breadcrumb: "@ui.breadcrumbs"
  }
}) {
  /*
    Must pass the IdeaContentLink model as model to the view (done by Marionette)
    along with the groupContent
   */
  initialize(options) {
    this.setLoading(true);
    this._groupContent = options.groupContent;
    this.messageView = options.messageView;
    this.canRender = false;
    var collectionManager = new CollectionManager();
    var that = this;

    Promise.join(
      this.model.getPostCreatorModelPromise(),
      that.model.getLinkCreatorModelPromise(),
      that.model.getIdeaModelPromise(),
      collectionManager.getUserLanguagePreferencesPromise(Ctx),
      function(postCreator, linkCreator, idea, langPrefs) {
        that.postCreator = postCreator;
        that.user = linkCreator;
        that.idea = idea;
        that.langPrefs = langPrefs;
        var ideaAncestry = that.idea.getAncestry();
        that.ideaAncestry = that.createIdeaNameCollection(ideaAncestry);
        const idExcerpt = that.model.get("idExcerpt")
        if (idExcerpt) {
            return idea.collection.collectionManager.getAllExtractsCollectionPromise(
            ).then(function(extracts){
              that.extract = extracts.get(idExcerpt);
              return that.extract.getCreatorModelPromise().then((creator)=>{
                that.extractHarvester = creator;
                that.canRender = true;
                that.onEndInitialization();
              })
            });
        } else {
          that.extractHarvester = null;
          that.extract = null;
          that.canRender = true;
          that.onEndInitialization();
        }
      }).error(function(e){
        console.error(e.statusText);
        //Render yourself in an ErrorView.
        //THIS IS HACKY
        that.model.failedToLoad = true;
      });
  }

  /*
    Override in child class in order to add logic once the promises are
    completed in initialization
   */
  onEndInitialization() {
  }

  /*
    Override in child class in order to add logic at the end of onRender
   */
  postRender() {}

  /*
    The function used by the template to render itself, given it's model
    @returns Function  The function that will be returned with parameter for model
   */
  serializerFunc() {
    var langPrefs = this.langPrefs;
    return function(model) {
      return model ? model.getShortTitleDisplayText(langPrefs) : "";
    };
  }

  onRender() {
    if (this.canRender) {

      if (! this.ideaAncestry) {
        throw new Error("Idea Ancestry Collection was undefined on message ", this.model.get('idPost'));
      }

      var IdeaBreadcrumbView = new BreadCrumbView.BreadcrumbCollectionView({
        collection: this.ideaAncestry,
        serializerFunc: this.serializerFunc(),
      });

      this.showChildView('breadcrumb', IdeaBreadcrumbView);
      this.postRender();
    }
  }

  /*
    Generates a collection containing the same idea models used in the CollectionManager
   */
  createIdeaNameCollection(ideaArray) {

    //Create an empty collection and populate it with the models in the Array
    //Shallow copy of the models. Hence, Idea changes should trigger change events on this collection
    //as well
    var col = new IdeaModel.Collection();
    _.each(ideaArray, function(idea){
      col.add(idea); //The order should be maintained
    });

    return col;
  }

  templateContext() {
    return {
      i18n: i18n,
      viewIdea: i18n.gettext("Go to this idea")
    };
  }

  onSeeIdeaClick() {
    var analytics = Analytics.getInstance();
    analytics.trackEvent(analytics.events.NAVIGATE_TO_IDEA_IN_IDEA_CLASSIFICATION);

    var panel = this.messageView.messageListView;
    Ctx.clearModal();
    openIdeaInModal(panel, this.idea, true, this.langPrefs);
  }
}

class DirectMessageView extends IdeaClassificationView.extend({
  template: '#tmpl-ideaClassification_directMessage'
}) {
  onEndInitialization() {
    this.setLoading(false);
    this.render();
  }

  serializeData() {
    if (!this.canRender) {
      return {};
    }

    return {
      author: this.user.get('name')
    }
  }
}

class DirectExtractView extends IdeaClassificationView.extend({
  template: '#tmpl-ideaClassification_directExtract'
}) {
  onEndInitialization() {
    this.setLoading(false);
    this.render();
  }

  serializeData() {
    if (!this.canRender) {
      return {};
    }

    return {
      harvester: this.user.get('name'),
      extractHarvester: this.extractHarvester.get('name'),
      extractText: this.extract.getQuote(),
      postAuthor: this.postCreator.get('name')
    }
  }
}

class IndirectMessageView extends IdeaClassificationView.extend({
  template: '#tmpl-ideaClassification_indirectMessage'
}) {
  onEndInitialization() {
    this.setLoading(false);
    this.render();
  }

  serializeData() {
    if (!this.canRender){
      return {};
    }

    return {
      author: this.user.get('name')
    }
  }
}

class IndirectExtractView extends IdeaClassificationView.extend({
  template: '#tmpl-ideaClassification_indirectExtract'
}) {
  onEndInitialization() {
    this.setLoading(false);
    this.render();
  }

  serializeData() {
    if (!this.canRender){
      return {};
    }

    return {
      harvester: this.user.get('name'),
      extractHarvester: this.extractHarvester.get('name'),
      extractText: this.extract.getQuote(),
      postAuthor: this.postCreator.get('name')
    }
  }
}

class ErrorView extends Marionette.View.extend({
  template: _.template("<div><%= i18n.gettext(\"Something went wrong in getting the contents of this idea. We are looking into it. Thank you for your patience.\") %></div>")
}) {
  initialize(options) {
    console.error("[IdeaClassificationModal] An error view was created on the idea content link", this.model.id);
  }

  serializeData() {
    return {
      i18n: i18n
    };
  }
}

class IdeaShowingMessageCollectionViewBody extends Marionette.CollectionView.extend({
  className: 'items'
}) {
  initialize(options) {
    this._groupContent = options.groupContent;
    this.messageView = options.messageView;
  }

  childViewOptions() {
    return {
      groupContent: this._groupContent,
      messageView: this.messageView
    }
  }

  childView(item) {

    //In the scenario that the View failed to initialize the models necessary
    //to parse this. An Error view should be made.
    if (_.has(item, 'failedToLoad') && item.failedToLoad === true) {
      return ErrorView;
    }

    if (item.isDirect()){
      if (item.get('@type') === Types.IDEA_RELATED_POST_LINK) {
        return DirectMessageView;
      }

      if (item.get('@type') === Types.IDEA_EXTRACT_LINK) {
        return DirectExtractView;
      }
      else {
        return ErrorView;
      }
    }

    else {
      if (item.get('@type') === Types.IDEA_RELATED_POST_LINK) {
        return IndirectMessageView;
      }

      if (item.get('@type') === Types.IDEA_EXTRACT_LINK) {
        return IndirectExtractView;
      }
      else {
        return ErrorView;
      }
    }
  }
}

class IdeaShowingMessageCollectionView extends Marionette.View.extend({
  template: '#tmpl-ideaClassification_collection',

  regions: {
    items: {
      el: '.items',
      replaceElement: true,
    }
  }
}) {
  initialize(options) {
    this._groupContent = options.groupContent;
    this.messageView = options.messageView;
  }

  onRender() {
    this.showChildView('items', new IdeaShowingMessageCollectionViewBody({
      collection: this.collection,
      groupContent: this._groupContent,
      messageView: this.messageView,
    }));
  }
}

class IdeasShowingMessageModal extends Backbone.Modal.extend({
  template: '#tmpl-ideaClassification_modal',
  className: 'modal-ideas-showing-message popin-wrapper',
  cancelEl: '.close, .js_close'
}) {
  initialize(options) {
    this.messageView = options.messageView;
    this.messageModel = options.messageModel, 
    this.ideaContentLinks = options.ideaContentLinks;
    this._groupContent = options.groupContent;
  }

  serializeData() {
    var number_of_ideas = this.ideaContentLinks.length;
    return {
      visible_because_msg: i18n.sprintf(
        i18n.ngettext(
            "This message is linked to the following idea because: ",
            "This message is linked to the %1$d following ideas because: ",
            number_of_ideas),
        number_of_ideas),
      title_msg: i18n.ngettext(
        "Link between this message and the idea",
        "Links between this message and ideas", number_of_ideas)
    };
  }

  onRender() {
    var IdeaClassificationCollectionView = new IdeaShowingMessageCollectionView({
      collection: this.ideaContentLinks,
      messageView: this.messageView,
      groupContent: this._groupContent
    });

    this.$(".ideas-reasons-collection").html(IdeaClassificationCollectionView.render().el);
  }
}

export default IdeasShowingMessageModal;
