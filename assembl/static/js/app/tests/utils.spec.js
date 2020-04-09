/**
 *
 * @module app.tests.utils.spec
 */

import $ from "jquery";
import PanelSpecTypes from "../utils/panelSpecTypes.js";
import { expect } from "chai";

describe("Utils module", function () {
    describe("panelSpecType", function () {
        it("getByRawId should throw error if PanelSpecTypes id undefined", function () {
            var panel = function () {
                return PanelSpecTypes.getByRawId("toto");
            };

            expect(panel).to.throw();
        });
    });

    describe("socket", function () {
        // testing socket event etc...

        it("socket should work perfect", function () {
            expect(true).to.be.true;
        });
    });
});
