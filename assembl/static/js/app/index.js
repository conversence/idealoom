/**
 * App instanciation.
 * @module app.index
 */

import * as Sentry from "@sentry/browser";
import * as Integrations from "@sentry/integrations";
import App from "./app.js";

import Router from "./router.js";
import Ctx from "./common/context.js";
import CollectionManager from "./common/collectionManager.js";

if (raven_url.length) {
    Sentry.init({
        dsn: raven_url,
        integrations: [
            new Integrations.CaptureConsole({
                levels: ["warn", "error", "assert"],
            }),
        ],
    });
    Sentry.setUserContext({ user_id: Ctx.getCurrentUserId() });
    window.Sentry = Sentry;
}

/**
 * Init current language
 * */
Ctx.initMomentJsLocale();

var router = new Router();
var collectionManager = new CollectionManager();
var socket = collectionManager.getConnectedSocketPromise();

window.Ctx = Ctx;

App.start();
