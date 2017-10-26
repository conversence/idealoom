/**
 * 
 * @module app.views.sourceEditView
 */
import Marionette from 'backbone.marionette';

import $ from 'jquery';
import i18n from '../utils/i18n.js';
import Promise from 'bluebird';
import Growl from '../utils/growl.js';


/**
 * An abstract class that defines the Marionette View
 * to use for the editing of each source in a source list
 * view.
 */
export default Marionette.View.extend({
  constructor: function exports() {
    Marionette.View.apply(this, arguments);
  },

    ui: {
        submit: '.js_saveSource',
    },

    events: {
        'click @ui.submit': 'submitForm'
    },

    submitForm: function(e) {
        e.preventDefault();
        this.saveModel();
    },

    /**
     * A function to override by sub-class to get the
     * model changed values
     * @returns Object of values for the model to change
     */
    fetchValues: function(){
        throw new Error("Cannot call fetchValues on an abstract class!");
    },

    saveModel: function(){
        var values = this.fetchValues();
        this.model.set(values);
        this.model.save(null, {
            success: function(model, resp){
                Growl.showBottomGrowl(Growl.GrowlReason.SUCCESS, i18n.gettext('Your settings were saved!'));
            },

            error: function(model, resp){
              Growl.showBottomGrowl(Growl.GrowlReason.ERROR, i18n.gettext('Your settings failed to update.'));  
            }
        });
    }
});
