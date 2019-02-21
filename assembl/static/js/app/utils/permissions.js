/**
 * 
 * @module app.utils.permissions
 */

var Permissions = {
  READ_USER_INFO: 'User.R.baseInfo',
  READ: 'Conversation.R',
  ADD_POST: 'Post.C',
  EDIT_POST: 'Post.U',
  DELETE_POST: 'Post.D',
  VOTE: 'Idea.C.Vote',
  ADD_EXTRACT: 'Content.C.Extract',
  EDIT_EXTRACT: 'Extract.U',
  ADD_IDEA: 'Idea.C',
  EDIT_IDEA: 'Idea.U',
  EDIT_SYNTHESIS: 'Synthesis.U',
  SEND_SYNTHESIS: 'Synthesis.U.send',
  SELF_REGISTER: 'Conversation.A.User',
  SELF_REGISTER_REQUEST: 'Conversation.A.User.request',
  ADMIN_DISCUSSION: 'Conversation.U',
  SYSADMIN: '*',
  EXPORT_EXTERNAL_SOURCE: 'Content.U.export',
  MODERATE: 'Content.U.moderate',
  DISC_STATS: 'Conversation.U.stats',
  OVERRIDE_SOCIAL_AUTOLOGIN: 'Conversation.A.User.override_autologin',
  ASSOCIATE_EXTRACT: 'Idea.A.Extract',
};

export default Permissions;
/*
 * Comment distinguer le cas où on n'a pas la permission:
 * ex: app.currentUser.can(Permissions.ADD_POST)
 * du cas ou l'usager est anonyme (déconnecté):
 * Ctx.getCurrentUser().isUnknownUser()
 */

