/**
 * 
 * @module app.views.synthesisMessage
 */

import Ctx from '../common/context.js';

import MessageView from './message.js';
import Synthesis from '../models/synthesis.js';
import SynthesisPanel from './synthesisPanel.js';
import CollectionManager from '../common/collectionManager.js';

/**
 * @class app.views.synthesisMessage.MessageView
 */
class SynthesisMessageView extends MessageView.extend({
  /**
   * The thread message template
   * @type {_.template}
   */
  template: Ctx.loadTemplate('message')
}) {
  /**
   * @init
   */
  initialize(obj) {
    super.initialize(...arguments);
    this.stopListening(this.messageListView, 'annotator:initComplete', this.onAnnotatorInitComplete);
    this.synthesisId = this.model.get('publishes_synthesis');
  }

  /**
   * Meant for derived classes to override
   * @type {}
   */
  transformDataBeforeRender(data) {
    data['subject'] = '';
    data['body'] = '';
    if (this.viewStyle == this.availableMessageViewStyles.PREVIEW) {
      data['bodyFormat'] = "text/plain";
    }

    return data;
  }

  /**
   * Meant for derived classes to override
   * @type {}
   */
  postRender() {
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
}

export default SynthesisMessageView;

