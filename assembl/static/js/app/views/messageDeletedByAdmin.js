/**
 *
 * @module app.views.message
 */

import i18n from "../utils/i18n.js";

import MessageDeletedByUserView from "./messageDeletedByUser.js";

/**
 * @class app.views.message.MessageDeletedByAdminView
 */
class MessageDeletedByAdminView extends MessageDeletedByUserView.extend({
    body: i18n.gettext("This message has been deleted by an administrator."),
}) {}

export default MessageDeletedByAdminView;
