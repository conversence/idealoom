/**
 * App instanciation.
 * @module app.index
 */

import App from "./app.js";

import Router from "./router.js";
import Ctx from "./common/context.js";
import CollectionManager from "./common/collectionManager.js";
import Raven from "raven-js";

/**
 * Init current language
 * */
Ctx.initMomentJsLocale();

if (raven_url.length) {
    Raven.config(raven_url, {
        ignoreErrors: [
            "AttributeError: 'ZMQRouter' object has no attribute 'loop'",
        ], //Squelch error untill https://github.com/mrjoes/sockjs-tornado/pull/67 goes through
    }).install();
    var userContext = { id: Ctx.getCurrentUserId() };
    if (Ctx.getCurrentUserId()) {
        userContext.user_id = Ctx.getCurrentUserId();
        // TODO: do we want to parametrize the old behaviour?
        // var user = Ctx.getCurrentUser();
        // userContext.name = user.get('name');
        // userContext.email = user.get('preferred_email');
    }
    Raven.setUserContext(userContext);

    window.Raven = Raven;
    require("raven-js/plugins/console.js");
} else {
    //Disables raven for development
    Raven.config(false);
    Raven.debug = true;
}

var router = new Router();
var collectionManager = new CollectionManager();
var socket = collectionManager.getConnectedSocketPromise();

window.Ctx = Ctx;

App.start();
