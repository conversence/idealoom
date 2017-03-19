'use strict';
/**
 * App initialization.
 * @module app.app
 */

var Marionette = require('backbone.marionette'),
    $ = require('jquery'),
    classlist = require('classlist-polyfill'),
    Raven = require('raven-js'),
    Radio = require('backbone.radio'),
    Types = require('./utils/types.js'),
    _ = require('underscore');


var RootView = Marionette.View.extend({
  el: 'body',
  regions: {
    headerRegions: '#header',
    infobarRegion: '#infobar',
    groupContainer: '#groupContainer',
    contentContainer: '#content-container',
    slider: '#slider',
  },
});


var AppClass = Marionette.Application.extend({
  onStart: function() {
    var that = this;
    this.rootView = new RootView();
    this.socket_vent = Radio.channel('socket');
    this.tour_vent = Radio.channel('tour');
    this.idea_vent = Radio.channel('ideas');
    this.message_vent = Radio.channel('messages');
    this.other_vent = Radio.channel('other');

    if (Backbone.history) {
      Backbone.history.start({
        pushState: true,
        root: '/' + $('#discussion-slug').val()
      });

      if (Backbone.history._hasPushState) {
        $(document).delegate("a", "click", function(evt) {
          var href = $(this).attr("href");
          var protocol = this.protocol + "//";

          // Note that we only care about assembl #tags.
          // We should prefix ours. For now, detect annotator.
          if (_.any(this.classList, function(cls) {
            return cls.indexOf('annotator-') === 0;
          })) return;
          if (typeof href !== 'undefined' && href.slice(protocol.length) !== protocol && /^#.+$/.test(href)) {
            evt.preventDefault();
            Backbone.history.navigate(href, true);
          }
        });
      }
    }
    // Temporary code for Catalyst demo
    function messageListener(event) {
      try {
        var data = event.data,
            dlen = data.length;
        if (dlen > 2 && data[dlen-2] == ",") {
          // bad json
          data = data.substring(0, dlen-2) + data[dlen-1];
        }
        data = JSON.parse(data);
        var ideaIdPrefix = 'local:' + Types.IDEA + '/';
        if (data.event == "click" && data.target.substring(0, ideaIdPrefix.length) === ideaIdPrefix) {
          // TODO: look for right group. Also handle Content.
          that.idea_vent.trigger('DEPRECATEDideaList:selectIdea', data.target);
        }
      } catch (e) {}
    }
    if (window.addEventListener){
      addEventListener("message", messageListener, false);
    } else {
      attachEvent("onmessage", messageListener);
    }

    if (activate_tour /*&& (currentUser.isUnknownUser() || currentUser.get('is_first_visit'))*/) {
      var TourManager = require('./utils/tourManager.js');
      this.tourManager = new TourManager();
    }

    // Tell Explorer not to cache Ajax requests.
    // http://stackoverflow.com/questions/4303829/how-to-prevent-a-jquery-ajax-request-from-caching-in-internet-explorer
    $.ajaxSetup({ cache: false });

    // change dynamically tab title
    document.title = document.querySelector('#discussion-topic').value; // not needed anymore on the debate page

    // change dynamically favicon in tab
    var link = document.createElement('link');
    link.type = 'image/x-icon';
    link.rel = 'shortcut icon';
    link.href = static_url + '/img/icon/infinite-1.png';
    document.getElementsByTagName('head')[0].appendChild(link);
  },
});


_.extend(Backbone.Marionette.View.prototype, {
  /*
   * Use to check if you should (re)render
   */
  isRenderedAndNotYetDestroyed: function() {
    return this.isRendered() && !this.isDestroyed();
  },

  listenTo: function() {
    var that = this;
    // Often, we listen on a promise in the initalizer. The view may already be dead.
    Raven.context(function() {
      if (that.isDestroyed()) {
        throw new Error("listenTo on a destroyed view");
      }
    });

    Object.getPrototypeOf(Backbone.Marionette.View.prototype).listenTo.apply(this, arguments);
  },

  listenToOnce: function() {
    var that = this;
    // Often, we listen on a promise in the initalizer. The view may already be dead.
    Raven.context(function() {
      if (that.isDestroyed()) {
        throw new Error("listenToOnce on a destroyed view");
      }
    });

    Object.getPrototypeOf(Backbone.Marionette.View.prototype).listenToOnce.apply(this, arguments);
  },
});

var App = new AppClass();

module.exports = App;
