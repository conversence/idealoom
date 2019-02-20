/**
 * 
 * @module app.utils.permissions
 */

var Permissions = {
  P_READ_USER_INFO = 'User.R.baseInfo'
  P_READ = 'Conversation.R'
  P_ADD_POST = 'Post.C'
  P_EDIT_POST = 'Post.U'
  P_DELETE_POST = 'Post.D'
  P_VOTE = 'Idea.C.Vote'
  P_ADD_EXTRACT = 'Content.C.Extract'
  P_EDIT_EXTRACT = 'Extract.U'
  P_ADD_IDEA = 'Idea.C'
  P_EDIT_IDEA = 'Idea.U'
  P_EDIT_SYNTHESIS = 'Synthesis.U'
  P_SEND_SYNTHESIS = 'Synthesis.U.send'
  P_SELF_REGISTER = 'Conversation.A.User'
  P_SELF_REGISTER_REQUEST = 'Conversation.A.User.request'
  P_ADMIN_DISC = 'Conversation.U'
  P_SYSADMIN = '*'
  P_EXPORT_EXTERNAL_SOURCE = 'Content.U.export'
  P_MODERATE = 'Content.U.moderate'
  P_DISC_STATS = 'Conversation.U.stats'
  P_OVERRIDE_SOCIAL_AUTOLOGIN = 'Conversation.A.User.override_autologin'
  P_ASSOCIATE_EXTRACT = 'Idea.A.Extract'
};

export default Permissions;
/*
 * Comment distinguer le cas où on n'a pas la permission:
 * ex: app.currentUser.can(Permissions.ADD_POST)
 * du cas ou l'usager est anonyme (déconnecté):
 * Ctx.getCurrentUser().isUnknownUser()
 */

