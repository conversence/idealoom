var Marionette = require('backbone.marionette');
/** LoaderView: a Marionette View that starts as a loader.
 */
var LoaderView = Marionette.View.extend({
  constructor: function LoaderView() {
    Marionette.View.apply(this, arguments);
  },
  isLoading: function() {
    return this.template === '#tmpl-loader';
  },
  setLoading: function(newVal, specialTemplate) {
    var specialTemplate;
    var current = this.isLoading();
    if (newVal) {
        if (!current) {
            this._template = this.template;
            this.template = '#tmpl-loader';
        }
        return !current;
    }
    specialTemplate = specialTemplate || this._template;
    if (current || specialTemplate !== this.template) {
        this.template = specialTemplate;
        // Disable the region clearing until merging of
        // https://github.com/marionettejs/backbone.marionette/pull/3426
        this._isRendered = false;
    }
    return current;
  },
});

module.exports = LoaderView;
