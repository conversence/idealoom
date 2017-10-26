/**
 * 
 * @module app.views.otherInIdeaList
 */

import Ctx from '../common/context.js';

import ideaInIdeaList from './ideaInIdeaList.js';
import IdeaView from './ideaInIdeaList.js';
import _ from 'underscore';

var otherInIdeaList = ideaInIdeaList.IdeaView.extend({
  constructor: function otherInIdeaList() {
    ideaInIdeaList.IdeaView.apply(this, arguments);
  },

  template: Ctx.loadTemplate('otherInIdeaList'),
  onRender: function() {
    Ctx.removeCurrentlyDisplayedTooltips(this.$el);

    var hasOrphanPosts = this.model.get('num_orphan_posts');
    var hasSynthesisPosts = this.model.get('num_synthesis_posts');

    var subMenu = _.find([hasOrphanPosts, hasSynthesisPosts], function(num) {
      return num !== 0;
    });

    if (typeof subMenu === 'undefined') {

      this.$el.addClass('hidden');
    } else {
      this.$el.removeClass('hidden');
    }

    this.$el.html(this.template);
    Ctx.initTooltips(this.$el);
  }
});

export default otherInIdeaList;
