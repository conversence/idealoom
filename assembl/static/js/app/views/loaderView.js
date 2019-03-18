import Marionette from 'backbone.marionette';

/** LoaderView: a Marionette View that starts as a loader.
 */
class LoaderView extends Marionette.View {
  isLoading() {
    return this.template === '#tmpl-loader';
  }

  setLoading(newVal, specialTemplate) {
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
  }
}

export default LoaderView;
