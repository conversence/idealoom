/**
 * @module app.models.accounts
 */
import Base from './base.js';

import Ctx from '../common/context.js';

/**
 * A user's (email or social) account.
 * Frontend model for :py:class:`assembl.models.auth.AbstractAgentAccount`
 * @class app.models.accounts.Account
 * @extends app.models.base.BaseModel
 */
class Account extends Base.Model.extend({
 /**
  * @member {string} app.models.accounts.Account.urlRoot
  */
 urlRoot: Ctx.getApiV2DiscussionUrl("/all_users/current/accounts"),

 /**
  * Defaults
  * @type {Object}
  */
 defaults: {
   //E-mail account specifics
   will_merge_if_validated: false,
   verified: false,
   profile: 0,
   preferred: false,
   //SocialAuthAccount specifics
   provider: null,
   username: null,
   picture_url: null,
   //Standards
   '@type': null,
   'email': null,
   '@id': null
 }
}) {
 /**
  * Validate the model attributes
  * @function app.models.accounts.Account.validate
  */
 validate(attrs, options) {
   /**
    * check typeof variable
    * */
 }

 /**
  * Returns true if the Account type is a Facebook account
  * @returns {Boolean}
  * @function app.models.accounts.Account.isFacebookAccount
  */
 isFacebookAccount() {
     return (this.get("@type") === 'FacebookAccount');
   }
}

/**
 * Accounts collection
 * @class app.models.accounts.Accounts
 * @extends app.models.base.BaseCollection
 */
class Accounts extends Base.Collection.extend({
 /**
  * @member {string} app.models.accounts.Accounts.url
  */
 url: Ctx.getApiV2DiscussionUrl("/all_users/current/accounts"),

 /**
  * The model
  * @type {Account}
  */
 model: Account
}) {
 /**
  * Returns true if the Account type is a Facebook account
  * @returns {Boolean}
  * @function app.models.accounts.Accounts.hasFacebookAccount
  */
 hasFacebookAccount() {
     var tmp = this.find(function(model) {
       return model.isFacebookAccount();
     });
     if (!tmp) return false;
     else return true;
   }

 /**
  * Returns Facebook account data
  * @returns {Object}
  * @function app.models.accounts.Accounts.getFacebookAccount
  */
 getFacebookAccount() {
     var tmp = this.find(function(model) {
       return model.isFacebookAccount();
     });
     if (!tmp) return null;
     else return tmp;
   }
}

export default {
  Model: Account,
  Collection: Accounts
};