/**
 * 
 * @module app.views.message
 */

import i18n from '../utils/i18n.js';

import MessageDeletedByUserView from './messageDeletedByUser.js';



/**
 * @class app.views.message.MessageDeletedByAdminView
 */
var MessageDeletedByAdminView = MessageDeletedByUserView.extend({
  constructor: function MessageDeletedByAdminView() {
    MessageDeletedByUserView.apply(this, arguments);
  },

  body: i18n.gettext("This message has been deleted by an administrator.")
});

export default MessageDeletedByAdminView;

