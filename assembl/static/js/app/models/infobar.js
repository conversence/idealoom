/**
 * Infobars for cookie and widget settings
 * @module app.models.infobar
 */
import Promise from 'bluebird';
import Base from './base.js';
import Widget from './widget.js';
import Ctx from '../common/context.js';
import CookiesManager from '../utils/cookiesManager.js';


const ViewNames = {
    WIDGET: "widget",
    COOKIE: "cookie",
    TOS: "tos",
}


/**
 * Info bar model
 * @class app.models.infobar.InfobarModel
 * @extends app.models.base.BaseModel
 */
var InfobarModel = Base.Model.extend({
/**
 * @function app.models.infobar.InfobarModel.constructor
 */
    constructor: function InfobarModel(){
        Base.Model.apply(this, arguments);
    },
    view_names: ViewNames
});

/**
 * Widget bar model
 * @class app.models.infobar.WidgetInfobarModel
 * @extends app.models.infobar.InfobarModel
 */
var WidgetInfobarModel = InfobarModel.extend({
    /**
     * @function app.models.infobar.WidgetInfobarModel.constructor
     */
    constructor: function WidgetInfobarModel(){
        Base.Model.apply(this, arguments);
    },
    view_name: ViewNames.WIDGET,
});

/**
 * Cookie bar model
 * @class app.models.infobar.CookieInfobarModel
 * @extends app.models.infobar.InfobarModel
 */
var CookieInfobarModel = InfobarModel.extend({
    /**
     * @function app.models.infobar.CookieInfobarModel.constructor
     */
    constructor: function CookieInfobarModel(){
        Base.Model.apply(this, arguments);
    },
    view_name: ViewNames.COOKIE,
});

/**
 * TOS bar model
 * @class app.models.infobar.TOSInfobarModel
 * @extends app.models.infobar.InfobarModel
 */
var TOSInfobarModel = InfobarModel.extend({
    /**
     * @function app.models.infobar.TOSInfobarModel.constructor
     */
    constructor: function TOSInfobarModel(){
        Base.Model.apply(this, arguments);
    },
    view_name: ViewNames.TOS,
});

/**
 * Cookie and widget bars collection
 * @class app.models.infobar.InfobarsCollection
 * @extends app.models.base.BaseCollection
 */
var InfobarsCollection = Base.Collection.extend({
/**
 * @function app.models.infobar.InfobarsCollection.constructor
 */
  constructor: function InfobarsCollection() {
    Base.Collection.apply(this, arguments);
  },
  view_names: ViewNames,
  createCollection: function(collectionManager, nextFunc) {
    collectionManager.getWidgetsForContextPromise(
            Widget.Model.prototype.INFO_BAR, null, ["closeInfobar"]).then(
        function(widgetCollection) {
          var discussionSettings = Ctx.getPreferences();
          var user = Ctx.getCurrentUser();
          var infobarsCollection = new InfobarsCollection();
          var isCookieUserChoice = CookiesManager.getUserCookiesAuthorization();
          if(!isCookieUserChoice && discussionSettings.cookies_banner){
            infobarsCollection.add(new CookieInfobarModel());
          }
          if (!user.isUnknownUser() && user.get('accepted_tos_version') != discussionSettings.tos_version) {
              infobarsCollection.add(new TOSInfobarModel());
          }
          widgetCollection.each(function(widgetModel){
            var model = new WidgetInfobarModel({widget: widgetModel});
            infobarsCollection.add(model);
          });
          nextFunc(infobarsCollection);
        });
  },
});

export default InfobarsCollection;