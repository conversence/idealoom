/**
 *
 * @module app.views.agent
 */

import Marionette from "backbone.marionette";

import IdeaLoom from "../app.js";
import _ from "underscore";
import $ from "jquery";
import Ctx from "../common/context.js";
import CollectionManager from "../common/collectionManager.js";
import i18n from "../utils/i18n.js";
import Permissions from "../utils/permissions.js";
import availableFilters from "./postFilters.js";

class AgentView extends Marionette.View.extend({
    ui: {
        avatar: ".js_agentAvatar",
        name: ".js_agentName",
    },

    events: {
        "click @ui.avatar": "onAvatarClick",
        "click @ui.name": "onAvatarClick",
    },
}) {
    serializeData() {
        return {
            i18n: i18n,
            show_email: Ctx.getCurrentUser().can(Permissions.ADMIN_DISCUSSION),
            agent: this.model,
        };
    }

    onRender() {
        Ctx.removeCurrentlyDisplayedTooltips(this.$el);
        Ctx.initTooltips(this.$el);
    }

    onAvatarClick(e) {
        e.stopPropagation();
        showUserMessages(this.model);
    }
}

class AgentAvatarView extends AgentView.extend({
    template: "#tmpl-agentAvatar",
    className: "agentAvatar",
    avatarSize: null,
}) {
    initialize(options) {
        if ("avatarSize" in options) {
            this.avatarSize = options.avatarSize;
        } else {
            this.avatarSize = 30;
        }
    }

    serializeData() {
        return {
            agent: this.model,
            avatarSize: this.avatarSize,
        };
    }
}

class AgentNameView extends AgentView.extend({
    template: "#tmpl-agentName",
    className: "agentName",
}) {}

function showUserMessages(userModel) {
    var filters = [
        { filterDef: availableFilters.POST_IS_FROM, value: userModel.id },
    ];
    var ModalGroup = require("./groups/modalGroup.js").default;
    var modal_title = i18n.sprintf(
        i18n.gettext("All messages by %s"),
        userModel.get("name")
    );
    var modalFactory = ModalGroup.filteredMessagePanelFactory(
        modal_title,
        filters
    );
    var modal = modalFactory.modal;
    var messageList = modalFactory.messageList;

    IdeaLoom.rootView.showChildView("slider", modal);
}

export default {
    AgentAvatarView: AgentAvatarView,
    AgentNameView: AgentNameView,
    showUserMessages: showUserMessages,
};
