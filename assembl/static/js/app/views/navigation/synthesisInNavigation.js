/**
 * 
 * @module app.views.navigation.synthesisInNavigation
 */

var Marionette = require('backbone.marionette');

var _ = require('underscore');
var $ = require('jquery');
var Promise = require('bluebird');
var AssemblPanel = require('../assemblPanel.js');
var CollectionManager = require('../../common/collectionManager.js');
var Types = require('../../utils/types.js');
var Assembl = require('../../app.js');
var Ctx = require('../../common/context.js');
var i18n = require('../../utils/i18n.js');
var PanelSpecTypes = require('../../utils/panelSpecTypes.js');
var scrollUtils = require('../../utils/scrollUtils.js');
var LoaderView = require('../loaderView.js');
var Analytics = require('../../internal_modules/analytics/dispatcher.js');

var SynthesisItem = LoaderView.extend({
  constructor: function SynthesisItem() {
    LoaderView.apply(this, arguments);
  },

  template: '#tmpl-synthesisItemInNavigation',
  initialize: function(options) {
    var that = this;
    this.setLoading(true);
    this.panel = options.panel;
    this.model.collection.collectionManager.getUserLanguagePreferencesPromise(Ctx).then(function(ulp) {
        that.translationData = ulp.getTranslationData();
        that.setLoading(false);
        that.render();
    });
  },
  events: {
    'click .js_synthesisList': 'onSelectedSynthesis'
  },
  serializeData: function() {
    if (this.isLoading()) {
        return {};
    }
    return {
      id: this.model.get('published_in_post'),
      subject: this.model.get('subject'),
      date: Ctx.formatDate(this.model.get('creation_date'))
    };
  },

  onSelectedSynthesis: function(e) {
    var messageId =  $(e.currentTarget).attr('data-message-id');
    this.panel.displaySynthesis(messageId);
    //If it's a small screen detected => scroll to the right
    if(Ctx.isSmallScreen()){
      var screenSize = window.innerWidth;
      scrollUtils.scrollToNextPanel('.groupsContainer',100,screenSize);
    }
  }

});

var SynthesisList = Marionette.CollectionView.extend({
  constructor: function SynthesisList() {
    Marionette.CollectionView.apply(this, arguments);
  },

  childView: SynthesisItem,
  initialize: function(options) {

    var publishedSyntheses = this.collection.getPublishedSyntheses();

    _.sortBy(publishedSyntheses, function(message) {
      return message.get('creation_date');
    });
    publishedSyntheses.reverse();

    this.collection = new Backbone.Collection(publishedSyntheses);

    this.childViewOptions = {
      panel: options.panel
    }
  }

});

var SynthesisInNavigationPanel = AssemblPanel.extend({
  constructor: function SynthesisInNavigationPanel() {
    AssemblPanel.apply(this, arguments);
  },

  template: '#tmpl-synthesisInNavigationPanel',
  panelType: PanelSpecTypes.NAVIGATION_PANEL_SYNTHESIS_SECTION,
  className: 'synthesisNavPanel',
  ui: {
    synthesisListHeader: ".synthesisListHeader"
  },
  regions:{
    synthesisContainer: '.synthesisList'
  },

  initialize: function(options) {
    AssemblPanel.prototype.initialize.apply(this, arguments);
    var that = this;
    var collectionManager = new CollectionManager();
    this.setLoading(true);

    Promise.join(collectionManager.getAllMessageStructureCollectionPromise(),
      collectionManager.getAllSynthesisCollectionPromise(),
      function(allMessageStructureCollection, allSynthesisCollection) {
      if(!that.isDestroyed()) {
        that.setLoading(false);
        that.allMessageStructureCollection = allMessageStructureCollection;
        that.allSynthesisCollection = allSynthesisCollection;
        that.render();
      }
    });
  },

  selectSynthesisInMenu: function(messageId) {
      $(".synthesisItem").closest('li').removeClass("selected");
      this.$(".synthesisItem[data-message-id=\"" + messageId + "\"]").addClass("selected");
    },

  displaySynthesis: function(messageId) {
    var analytics = Analytics.getInstance();

    analytics.trackEvent(analytics.events.NAVIGATION_OPEN_SPECIFIC_SYNTHESIS);
    var messageListView = this.getContainingGroup().findViewByType(PanelSpecTypes.MESSAGE_LIST);
    messageListView.currentQuery.clearAllFilters();
    messageListView.toggleFilterByPostId(messageId);
    messageListView.showMessageById(messageId, undefined, false);

    setTimeout(function(){
      if ( messageListView.ui.stickyBar ){
        messageListView.ui.stickyBar.addClass('hidden');
      }
      if ( messageListView.ui.replyBox ){
        messageListView.ui.replyBox.addClass('hidden');
      }
    }, 1);

    // Show that entry is selected
    this.selectSynthesisInMenu(messageId);
  },

  displaySynthesisList: function(allMessageStructureCollection, allSynthesisCollection) {
      var lastPublisedSynthesis = allSynthesisCollection.getLastPublisedSynthesis();

      if (lastPublisedSynthesis) {

        var synthesisList = new SynthesisList({
          collection: allSynthesisCollection,
          panel: this
        });

        this.showChildView('synthesisContainer', synthesisList);
        this.displaySynthesis(lastPublisedSynthesis.get('published_in_post'));
      }
      else {
        this.ui.synthesisListHeader.html(i18n.gettext("No synthesis of the discussion has been published yet"));
      }
    },

  onRender: function() {
    var that = this;
    var collectionManager = new CollectionManager();

    if (!this.isLoading() && !this.isDestroyed()) {
        this.displaySynthesisList(this.allMessageStructureCollection, this.allSynthesisCollection);
        this.listenTo(this.allSynthesisCollection, 'add reset', function() {
          //console.log("Re-displaying synthesis list from collection update...", allSynthesisCollection.length);
          that.displaySynthesisList(that.allMessageStructureCollection, that.allSynthesisCollection);
        });
        // that.getRegion('synthesisContainer').$el.find(".synthesisItem:first")[0].id = "tour_step_synthesis_item1";
        // Assembl.tour_vent.trigger("requestTour", "synthesis_item1");
    }
  },

});

module.exports = SynthesisInNavigationPanel;
