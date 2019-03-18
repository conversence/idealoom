/**
 * Button to switch to less/more filter options
 * @module app.models.flipSwitchButton
 */
import Backbone from 'backbone';

/**
 * Flip switch button model
 * @class app.models.flipSwitchButton.FlipSwitchButtonModel
 */
class FlipSwitchButtonModel extends Backbone.Model.extend({
 /**
  * Defaults
  * @type {Object}
  */
 defaults: {
   'isOn': false,
   'labelOn': 'on',
   'labelOff': 'off'
 }
}) {
 /**
  * Validate the model attributes
  * @function app.models.discussionSource.sourceModel.validate
  */
 validate(attrs, options) {
   if (attrs.isOn !== false && attrs.isOne !== true)
       return "isOn attribute should be a boolean";
   return;
 }
}

export default FlipSwitchButtonModel;
