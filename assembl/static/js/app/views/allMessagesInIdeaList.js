/**
 * 
 * @module app.views.allMessagesInIdeaList
 */

import $ from 'jquery';
import ideaInIdeaList from './ideaInIdeaList.js';
import Ctx from '../common/context.js';
import PanelSpecTypes from '../utils/panelSpecTypes.js';

class AllMessagesInIdeaListView extends ideaInIdeaList.IdeaView.extend({
  /**
   * The template
   * @type {template}
   */
  template: Ctx.loadTemplate('allMessagesInIdeaList'),

  /**
   * @events
   */
  events: {
    'click .idealist-title': 'onTitleClick'
  }
}) {
  /**
   * The render
   */
  onRender() {
    Ctx.removeCurrentlyDisplayedTooltips(this.$el);
    var data = this.model.toJSON();

    this.$el.addClass('idealist-item');
    if (false && this.model.get('num_posts') == 0) { // why hiding it? it becomes impossible to post outside of an idea, at the beginning of a debate
      this.$el.addClass('hidden');
    }
    else {
      this.$el.removeClass('hidden');
    }

    data.Ctx = Ctx;

    this.$el.html(this.template(data));
    Ctx.initTooltips(this.$el);
    return this;
  }

  /**
   * @event
   */
  onTitleClick() {
    $('.idealist-item').removeClass('is-selected');

    this._groupContent.setCurrentIdea(null);

    // Quentin: Where else could we put this code so that it can be called by several things?
    // I had to duplicate this code into views/messageSend.js
    var messageListView = this._groupContent.findViewByType(PanelSpecTypes.MESSAGE_LIST);

    messageListView.triggerMethod('messageList:clearAllFilters');

    //Yes, this will cause double-renders in some cases.  Will be fixed once messageList observes it's result list.
    messageListView.render();

    this.$el.addClass('is-selected');
  }
}

export default AllMessagesInIdeaListView;
