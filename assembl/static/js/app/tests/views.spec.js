/**
 *
 * @module app.tests.views.spec
 */

import { expect } from "chai";
import ViewsFactory from "../objects/viewsFactory.js";
import CollectionManager from "../common/collectionManager.js";
import GroupState from "../models/groupState.js";
import messageList from "../views/messageList.js";
import groupContainer from "../views/groups/groupContainer.js";
import $ from "jquery";
import mockServer from "./mock_server.js";

var currentView;
var collectionManager = new CollectionManager();

describe("Views Specs", function () {
    /*
  describe('Navbar', function() {
    it('Views should exist', function() {
      currentView.ui.joinDiscussion.click()
      expect($('#slider')).to.have.html('<div class="generic-modal popin-wrapper modal-joinDiscussion bbm-wrapper"></div>');
    });
  });
  */

    describe("Message list", function () {
        beforeEach(function (done) {
            mockServer.setupMockAjax();
            collectionManager
                .getGroupSpecsCollectionPromise(ViewsFactory, undefined, true)
                .then(function (groupSpecs) {
                    currentView = new groupContainer({
                        collection: groupSpecs,
                    });
                    $("#test_view").html(currentView.render().el);
                    done();
                })
                .catch(function (err) {
                    done(err);
                });
        });

        afterEach(function () {
            $("#test_view").html("");
            mockServer.tearDownMockAjax();
        });

        it("View should exist", function () {
            console.log(currentView.el);
            expect(currentView.el).to.be.ok;
        });
    });
});
