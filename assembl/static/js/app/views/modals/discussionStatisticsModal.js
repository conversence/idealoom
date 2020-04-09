/**
 *
 * @module app.views.discussionStatisticsModal
 */
import Backbone from "backbone";

import Marionette from "backbone.marionette";
import i18n from "../../utils/i18n.js";
import $ from "jquery";
import _ from "underscore";
import Permissions from "../../utils/permissions.js";
import Ctx from "../../common/context.js";

class StatsModal extends Backbone.Modal.extend({
    template: "#tmpl-discussionStatisticsModal",
    className: "group-modal popin-wrapper",
    cancelEl: ".js_close",
    keyControl: false,

    events: {
        "click #get_stats": "getStats",
        "click #get_participant_stats": "getParticipantStats",
    },

    participantFields: [
        "posts",
        "cumulative_posts",
        "liking",
        "cumulative_liking",
        "liked",
        "cumulative_liked",
        "replies_received",
        "cumulative_replies_received",
        "active",
    ],
}) {
    initialize(options) {
        Ctx.setCurrentModalView(this);
    }

    serializeData() {
        return {
            isDiscussionAdmin: Ctx.getCurrentUser().can(
                Permissions.ADMIN_DISCUSSION
            ),
        };
    }

    doDownload(url, filename) {
        // TODO: This will probably fail in IE, see
        // http://stackoverflow.com/questions/13405129/javascript-create-and-save-file
        var el = this.$el;

        var a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.class = "hidden";
        a.id = "hidden_href";
        el.append(a);
        a.click();
        setTimeout(function () {
            el.find("#hidden_href").remove();
        }, 0);
    }

    addCommonStats(url) {
        var separator = "?";
        var fields = this.$el.find("fieldset");
        var val = fields.children("#start_date").val();
        if (val) {
            url += separator + "start=" + val;
            separator = "&";
        }
        val = fields.children("#end_date").val();
        if (val) {
            url += separator + "end=" + val;
            separator = "&";
        }
        val = fields.children("#interval").val();
        if (val) {
            url += separator + "interval=" + val;
            separator = "&";
        }
        val = fields.children("#format").val();
        if (val) {
            url += separator + "format=" + val;
            separator = "&";
        }
        return url;
    }

    checkDates() {
        var fields = this.$el.find("fieldset");
        var startDate = fields.children("#start_date").val();
        var endDate = fields.children("#end_date").val();
        if (endDate <= startDate) {
            alert(_("The end date should be later than the start date"));
        }
        return endDate > startDate;
    }

    getStats(ev) {
        if (!this.checkDates()) {
            ev.preventDefault();
            return;
        }
        try {
            var url = "/time_series_analytics";
            url = this.addCommonStats(url);
            url = Ctx.getApiV2DiscussionUrl(url);
            this.doDownload(
                url,
                Ctx.getDiscussionSlug() +
                    "_stats." +
                    this.$el.find("#format").val()
            );
        } catch (e) {
            alert(e);
        }
        ev.preventDefault();
    }

    getParticipantStats(ev) {
        if (!this.checkDates()) {
            ev.preventDefault();
            return;
        }
        var val;
        var separator = "?";
        var fields = this.$el.find("fieldset");
        var url = "/participant_time_series_analytics";
        try {
            url = this.addCommonStats(url);
            if (url.indexOf(separator) > 0) {
                separator = "&";
            }
            for (var i = 0; i < this.participantFields.length; i++) {
                val = this.participantFields[i];
                var field = fields.find("#field_" + val);
                if (field.length && field[0].checked) {
                    url += separator + "data=" + val;
                    separator = "&";
                }
            }
            val = fields.find("#show_emails");
            if (val.length) {
                url += separator + "show_emails=" + String(!!val[0].checked);
                separator = "&";
            }
            val = fields.children("#sort").val();
            if (val) {
                url += separator + "sort=" + val;
                separator = "&";
            }
            url = Ctx.getApiV2DiscussionUrl(url);
            this.doDownload(
                url,
                Ctx.getDiscussionSlug() +
                    "_participant_stats." +
                    fields.children("#format").val()
            );
        } catch (e) {
            alert(e);
        }
        ev.preventDefault();
    }
}

export default StatsModal;
