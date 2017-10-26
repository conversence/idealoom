/**
 * 
 * @module app.views.authorization
 */

import Marionette from 'backbone.marionette';

import Ctx from '../common/context.js';

var authorization = Marionette.View.extend({
  constructor: function authorization() {
    Marionette.View.apply(this, arguments);
  },

  template: '#tmpl-authorization',
  className: 'authorization',
  initialize: function(options) {
    this.error = options.error;
    this.message = options.message;
  },
  serializeData: function() {
      return {
        error: this.error,
        message: this.message
      }
    },
  templateContext: function() {
    return {
      urlLogIn: function() {
        return '/login?next=/' + Ctx.getDiscussionSlug() + '/';
      }
    }
  }
});

export default authorization;
