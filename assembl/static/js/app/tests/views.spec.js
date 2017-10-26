/**
 * 
 * @module app.tests.views.spec
 */

var expect = require('chai').expect;

var ViewsFactory = require('../objects/viewsFactory.js');
var CollectionManager = require('../common/collectionManager.js');
var GroupState = require('../models/groupState.js');
var messageList = require('../views/messageList.js');
var groupContainer = require('../views/groups/groupContainer.js');
var $ = require('jquery');
var mockServer = require('./mock_server.js');

var currentView;
var collectionManager = new CollectionManager();

describe('Views Specs', function() {

  /*
  describe('Navbar', function() {
    it('Views should exist', function() {
      currentView.ui.joinDiscussion.click()
      expect($('#slider')).to.have.html('<div class="generic-modal popin-wrapper modal-joinDiscussion bbm-wrapper"></div>');
    });
  });
  */

  describe('Message list', function() {
    beforeEach(function(done) {
      mockServer.setupMockAjax();
      collectionManager.getGroupSpecsCollectionPromise(
        ViewsFactory, undefined, true).then(function(groupSpecs) {
        currentView = new groupContainer({collection: groupSpecs});
        $('#test_view').html(currentView.render().el);
        done();
      }).catch(function(err) {
          done(err);
      });
    });

    afterEach(function() {
      $('#test_view').html("");
      mockServer.tearDownMockAjax();
    });

    it('View should exist', function() {
      console.log(currentView.el);
      expect(currentView.el).to.be.ok;
    });
  });
});
