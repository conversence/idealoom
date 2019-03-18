/**
 * 
 * @module app.views.messageModerationOptions
 */

import Backbone from 'backbone';

import Marionette from 'backbone.marionette';
import IdeaLoom from '../app.js';
import _ from 'underscore';
import $ from 'jquery';
import Ctx from '../common/context.js';
import AgentViews from './agent.js';
import i18n from '../utils/i18n.js';


class messageModerationOptions extends Marionette.View.extend({
  template: '#tmpl-messageModerationOptions',
  className: 'messageModerationOptions',

  ui: {
    publicationStatusSelect: '.js_messagePublicationStatusSelect',
    moderationDetails: '.js_moderationDetails',
    messageModerator: '.js_messageModerator',
    messageModeratorAvatar: '.js_messageModerator .js_avatarContainer',
    messageModeratorName: '.js_messageModerator .js_nameContainer',
    messageModeratedVersion: '.js_messageModeratedVersion',
    messageModerationRemarks: '.js_messageModerationRemarks',
    saveButton: '.js_messageModerationSaveButton',
    cancelButton: '.js_messageModerationCancelButton'
  },

  events: {
    'change @ui.publicationStatusSelect': 'onPublicationStatusSelectChange',
    'click @ui.saveButton': 'onSaveButtonClick',
    'click @ui.cancelButton': 'onCancelButtonClick'
  }
}) {
  initialize(options) {
    //console.log("messageModerationOptions::initialize() options: ", options);
    this.options = options;

    if ( !("message_publication_status" in options) ){
      this.options.message_publication_status = "PUBLISHED";
    }

    if ( !("message_moderated_version" in options) ){
      this.options.message_moderated_version = Ctx.getPreferences().moderation_template;
    }
    
    if ( !("message_moderation_remarks" in options) ){
      this.options.message_moderation_remarks = "";
    }

    if ( !("message_original_body_safe" in options) ){
      this.options.message_original_body_safe = "";
    }
  }

  onRender() {
    var that = this;

    this.updateContent();

    if ( this.model.get("moderator") ){
      this.model.getModeratorPromise().then(function(messageModerator){
        var agentAvatarView = new AgentViews.AgentAvatarView({
          model: messageModerator
        });
        that.ui.messageModeratorAvatar.html(agentAvatarView.render().el);

        var agentNameView = new AgentViews.AgentNameView({
          model: messageModerator
        });
        that.ui.messageModeratorName.html(agentNameView.render().el);
      });
    }
  }

  onPublicationStatusSelectChange(ev) {
    this.updateContent();
  }

  updateContent() {
    if ( this.ui.publicationStatusSelect.val() == "PUBLISHED" ){
      this.ui.moderationDetails.addClass("hidden");
    }
    else {
      this.ui.moderationDetails.removeClass("hidden");
    }

    if ( this.model.get("moderator") ){
      this.ui.messageModerator.removeClass('hidden');
    }
    else {
      this.ui.messageModerator.addClass("hidden");
    }
  }

  onSaveButtonClick() {
    var publication_state = this.ui.publicationStatusSelect.val();
    if ( publication_state == "PUBLISHED" ){
      this.model.save({
        publication_state: publication_state
      }, {patch: true}); // send a PATCH request, not a PUT
    }
    else {
      this.model.save({
        publication_state: publication_state,
        moderation_text: this.ui.messageModeratedVersion.val(),
        moderator_comment: this.ui.messageModerationRemarks.val()
      }, {patch: true}); // send a PATCH request, not a PUT
    }
    this.trigger("moderationOptionsSave");
    this.trigger("moderationOptionsClose");
  }

  onCancelButtonClick() {
    this.trigger("moderationOptionsClose");
  }

  serializeData() {
    return {
      i18n: i18n,
      message_publication_status: this.options.message_publication_status,
      message_moderated_version: this.options.message_moderated_version,
      message_moderation_remarks: this.options.message_moderation_remarks,
      message_original_body_safe: this.options.message_original_body_safe
    }
  }
}

export default messageModerationOptions;
