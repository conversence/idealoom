/**
 *
 * @module app.utils.growl
 */
import $ from "jquery";
import _ from "underscore";
window.jQuery = $;
import growl from "bootstrap-notify";

/*
    An easy to use growling function for use in IdeaLoom

    If an alternative growling method is desired, please extend this file
    and sprinkle across code-base accordingly
 */
var GrowlReason = {
    SUCCESS: "success",
    ERROR: "danger",
};

var defaultGrowlSettings = {
    element: "body",
    // type: either 'success' or 'error'
    placement: {
        from: "bottom",
        align: "right",
    },
    offset: 20,
    delay: 4000,
    allow_dismiss: true,
    spacing: 10,
};

var showBottomGrowl = function (growl_reason, msg, settings) {
    var mergedSettings = _.extend(defaultGrowlSettings, {
        type: growl_reason,
    });
    mergedSettings = _.extend(mergedSettings, settings);
    $.notify({ message: msg }, mergedSettings);
};

export default {
    GrowlReason: GrowlReason,
    showBottomGrowl: showBottomGrowl,
};
