/**
 * A partner organization, to be displayed in front page
 * @module app.models.partners
 */

import $ from 'jquery';
import Base from './base.js';
import i18n from '../utils/i18n.js';
import Ctx from '../common/context.js';


/**
 * Partner model
 * Frontend model for :py:class:`assembl.models.auth.PartnerOrganization`
 * @class app.models.partners.PartnerOrganizationModel
 * @extends app.models.base.BaseModel
 */
class PartnerOrganizationModel extends Base.Model.extend({
 /**
  * @type {string}
  */
 urlRoot: Ctx.getApiV2DiscussionUrl('partner_organizations'),

 /**
  * Defaults
  * @type {Object}
  */

 defaults: {
   name: '',
   description: '',
   homepage: '',
   logo: '',
   is_initiator: false
 }
}) {
 validate(attrs, options) {
   /**
    * check typeof variable
    * */
    
 }
}

/**
 * Partner collection
 * @class app.models.partners.PartnerOrganizationCollection
 * @extends app.models.base.BaseCollection
 */
class PartnerOrganizationCollection extends Base.Collection.extend({
 /**
  * @type {string}
  */
 url: Ctx.getApiV2DiscussionUrl('partner_organizations'),

 /**
  * The model
  * @type {PartnerOrganizationModel}
  */
 model: PartnerOrganizationModel
}) {}

export default {
  Model: PartnerOrganizationModel,
  Collection: PartnerOrganizationCollection
};
