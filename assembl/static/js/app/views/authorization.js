/**
 * 
 * @module app.views.authorization
 */

import Marionette from 'backbone.marionette';

import Ctx from '../common/context.js';

class authorization extends Marionette.View.extend({
  template: '#tmpl-authorization',
  className: 'authorization'
}) {
  initialize(options) {
    this.error = options.error;
    this.message = options.message;
  }

  serializeData() {
      return {
        error: this.error,
        message: this.message
      }
    }

  templateContext() {
    return {
      urlLogIn: function() {
        return '/login?next=/' + Ctx.getDiscussionSlug() + '/';
      }
    }
  }
}

export default authorization;
