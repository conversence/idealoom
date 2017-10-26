/**
 * 
 * @module app.views.synthesisMessage
 */

var Ctx = require('../common/context.js');

var MessageView = require('./message.js');
var Synthesis = require('../models/synthesis.js');
var SynthesisPanel = require('./synthesisPanel.js');
var CollectionManager = require('../common/collectionManager.js');

/**
 * @class app.views.synthesisMessage.MessageView
 */
var SynthesisMessageView = MessageView.extend({
  constructor: function SynthesisMessageView() {
    MessageView.apply(this, arguments);
  },

  /**
   * @init
   */
  initialize: function(obj) {
    MessageView.prototype.initialize.apply(this, arguments);
    this.stopListening(this.messageListView, 'annotator:initComplete', this.onAnnotatorInitComplete);
    this.synthesisId = this.model.get('publishes_synthesis');
  },

  /**
   * The thread message template
   * @type {_.template}
   */
  template: Ctx.loadTemplate('message'),

  /**
   * Meant for derived classes to override
   * @type {}
   */
  transformDataBeforeRender: function(data) {
    data['subject'] = '';
    data['body'] = '';
    if (this.viewStyle == this.availableMessageViewStyles.PREVIEW) {
      data['bodyFormat'] = "text/plain";
    }

    return data;
  },
  /**
   * Meant for derived classes to override
   * @type {}
   */
  postRender: function() {
    var that = this;
    var body;
    var collectionManager = new CollectionManager();

    collectionManager.getAllSynthesisCollectionPromise()
      .then(function(allSynthesisCollection) {
        var synthesis = allSynthesisCollection.get(that.synthesisId);
        if (!synthesis) {
          throw Error("BUG: Could not get synthesis after post. Maybe too early.")
        }

        that.$('.message-subject').html(synthesis.get('subject'));
        if (that.viewStyle == that.availableMessageViewStyles.PREVIEW) {
          //Strip HTML from preview
          //bodyFormat = "text/plain";

          body = MessageView.prototype.generateBodyPreview(synthesis.get('introduction'));
          that.$('.message-body > p').empty().html(body);
        }
        else {
          that.synthesisPanel = new SynthesisPanel({
            model: synthesis,
            messageListView: that.messageListView,
            panelWrapper: that.messageListView.getPanelWrapper(),
            el: that.$('.message-body'),
            template: '#tmpl-synthesisPanelMessage',
            showAsMessage: true
          });
          that.synthesisPanel.render();
        }
      });
    this.$(".message-body").removeClass('js_messageBodyAnnotatorSelectionAllowed');

    return;
  }

});

module.exports = SynthesisMessageView;

