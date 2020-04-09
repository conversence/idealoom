/**
 *
 * @module app.utils.socket
 */

import _ from "underscore";
import SockJS from "sockjs-client";

import App from "../app.js";
import Ctx from "../common/context.js";

/**
 * @class app.utils.socket.Socket
 *
 * @param {string} url
 */
var Socket = function (connectCallback, collManager) {
    this.connectCallback = connectCallback;
    this.collectionManager = collManager;
    if (start_application) {
        this.init();
    }
};

/**
 * @const
 */
Socket.RECONNECTION_WAIT_TIME = 5000;

/**
 * @init
 */
Socket.prototype.init = function () {
    if (Ctx.debugSocket) {
        console.log("Socket::init()");
    }
    this.socket = new SockJS(Ctx.getSocketUrl());
    this.socket.onopen = this.onOpen.bind(this);
    this.socket.onmessage = this.onMessage.bind(this);
    this.socket.onclose = this.onClose.bind(this);
    this.socket.onerror = this.onError.bind(this);
    if (Ctx.debugSocket) {
        console.log("Socket::init() state is now STATE_CLOSED");
    }
    this.state = SockJS.CLOSED;
};

/**
 * Triggered when the connection opens
 *
 * Note that the actual backbone event App.socket_vent.trigger('socket:open')
 * is actually sent in Socket.prototype.onMessage
 * @event
 */
Socket.prototype.onOpen = function (ev) {
    if (Ctx.debugSocket) {
        console.log("Socket::onOpen()");
    }
    this.socket.send("token:" + Ctx.getCsrfToken());
    this.socket.send("discussion:" + Ctx.getDiscussionId());
    if (Ctx.debugSocket) {
        console.log("Socket::onOpen() state is now STATE_CONNECTING");
    }
    this.state = SockJS.CONNECTING;
};

/**
 * Triggered when a socket error occurs
 * @event
 */
Socket.prototype.onError = function (ev) {
    if (true || Ctx.debugSocket) {
        console.log("Socket::onError() an error occured in the websocket");
    }
};

/**
 * Triggered when the client receives a message from the server
 * @event
 */
Socket.prototype.onMessage = function (ev) {
    if (Ctx.debugSocket) {
        console.log("Socket::onMessage()");
    }
    if (this.state === SockJS.CONNECTING) {
        this.connectCallback(this);
        App.socket_vent.trigger("socket:open");
        if (Ctx.debugSocket) {
            console.log("Socket::onOpen() state is now STATE_OPEN");
        }
        this.state = SockJS.OPEN;
    }

    var data = JSON.parse(ev.data);
    var i = 0;
    var len = data.length;

    for (; i < len; i += 1) {
        this.processData(data[i]);
    }

    //App.socket_vent.trigger('socket:message');
};

/**
 * Triggered when the connection closes ( or lost the connection )
 * @event
 */
Socket.prototype.onClose = function (ev) {
    if (Ctx.debugSocket) {
        console.log("Socket::onClose()");
    }
    if (Ctx.debugSocket) {
        console.log("Socket::onClose() state is now STATE_CLOSED");
    }
    this.state = SockJS.CLOSED;
    App.socket_vent.trigger("socket:close");

    var that = this;
    window.setTimeout(function () {
        if (Ctx.debugSocket) {
            console.log("Socket::onClose() attempting to reconnect");
        }
        that.init();
    }, Socket.RECONNECTION_WAIT_TIME);
};

/**
 * Processes one item from a data array from the server
 * @param  {Object} item
 */
Socket.prototype.processData = function (item) {
    var collPromise = this.collectionManager.getCollectionPromiseByType(item);

    if (Ctx.debugSocket) {
        console.log("On socket:", item["@type"], item["@id"], item);
    }

    if (collPromise === null) {
        if (item["@type"] == "Connection") {
            //Ignore Connections
            return;
        } else {
            if (Ctx.debugSocket) {
                console.log(
                    "Socket.prototype.processData(): TODO: Handle socket events for items of type:",
                    item["@type"],
                    item
                );
            }
            return;
        }
    }

    // Each collection must know what to do
    collPromise.done(function (collection) {
        collection.updateFromSocket(item);
    });
};

export default Socket;
