'use strict';
/**
 * 
 * @module app.views.authorization
 */

var Marionette = require('backbone.marionette'),
    Ctx = require('../common/context.js');

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

module.exports = authorization;
