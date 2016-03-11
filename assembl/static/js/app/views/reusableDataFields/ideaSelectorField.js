'use strict';

var Marionette = require('../../shims/marionette.js'),
    _ = require('../../shims/underscore.js'),
    Assembl = require('../../app.js'),
    Ctx = require('../../common/context.js'),
    CollectionManager = require('../../common/collectionManager.js'),
    Promise = require('bluebird'),
    ObjectTreeRenderVisitor = require('../visitors/objectTreeRenderVisitor.js'),
    IdeaSiblingChainVisitor = require('../visitors/ideaSiblingChainVisitor'),
    IdeaModel = require('../../models/idea.js');
//require("../../../bower/bootstrap-treeview/dist/bootstrap-treeview.min.js"); // this is already loaded by gulp "libs" task

var IdeaSelectorField = Marionette.ItemView.extend({ //var IdeaSelectorField = Marionette.CollectionView.extend({
  constructor: function IdeaSelectorField() {
    Marionette.ItemView.apply(this, arguments); //Marionette.CollectionView.apply(this, arguments);
  },

  template: _.template(""),
  className: "idea-selector",
  initialize: function(options) {
    console.log("IdeaSelectorField::initialize();");
    var that = this;

    this.collection = "collection" in options ? options.collection : new IdeaModel.Collection();

    var collectionManager = new CollectionManager();
    this.treeData = [];

    Promise.join(
      collectionManager.getAllIdeasCollectionPromise(),
      collectionManager.getAllIdeaLinksCollectionPromise(),
      function(allIdeasCollection, allIdeaLinksCollection) {
        console.log("allIdeasCollection: ", allIdeasCollection);
        console.log("allIdeaLinksCollection: ", allIdeaLinksCollection);
        var rootIdea = null;
        var view_data = {};
        var order_lookup_table = [];
        var roots = [];

        that.allIdeasCollection = allIdeasCollection;
        that.allIdeaLinksCollection = allIdeaLinksCollection;

        rootIdea = that.allIdeasCollection.getRootIdea();

        function excludeRoot(idea) {
          return idea != rootIdea && !idea.hidden;
        }

        that.allIdeasCollection.visitDepthFirst(that.allIdeaLinksCollection, new ObjectTreeRenderVisitor(view_data, order_lookup_table, roots, excludeRoot), rootIdea.getId());
        that.allIdeasCollection.visitDepthFirst(that.allIdeaLinksCollection, new IdeaSiblingChainVisitor(view_data), rootIdea.getId());

        function addIdeaToTree(idea, view_data, tree){
          var ideaItem = {
            "text": idea.getShortTitleDisplayText(),
            "model": idea
          };

          ideaItem.state = {};
          ideaItem.state.expanded = true;
          // set idea as checked and selected if it is part of the collection which was given in constructor
          if ( that.collection.findWhere({ '@id': idea.getId() }) ){
            ideaItem.state.checked = true;
            ideaItem.state.selected = true;
          }

          tree.push(ideaItem);
          var data = view_data[idea.getId()];
          if ( data && "children" in data && data.children.length ){
            ideaItem.nodes = [];
            _.each(data.children, function(child){
              addIdeaToTree(child, view_data, ideaItem.nodes);
            });
          }
        };

        _.each(roots, function(idea) { // idea is the model of an idea
          addIdeaToTree(idea, view_data, that.treeData);
        });
        if(!that.isViewDestroyed()) {
          that.render();
        }
      }
    );
  },

  onRender: function() {
    var that = this;

    this.$el.empty();
    
    var checkableTreeviewClass = "treeview-checkable";
    var checkableTreeviewOutputClass = "treeview-checkable-output";

    var checkableTableOfIdeas = $("<div></div>");
    checkableTableOfIdeas.addClass(checkableTreeviewClass);

    var output = $("<div></div>");
    output.addClass(checkableTreeviewOutputClass);

    var checkableTree = checkableTableOfIdeas.treeview({
      data: that.treeData,
      showIcon: false,
      showCheckbox: true,
      multiSelect: true,
      onNodeChecked: function(event, node) {
        checkableTableOfIdeas.treeview('selectNode', node.nodeId);
        that.collection.add(node.model);

        output.prepend('<p>' + node.text + ' was checked</p>');
        console.log("that.collection: ", that.collection);
      },
      onNodeUnchecked: function (event, node) {
        checkableTableOfIdeas.treeview('unselectNode', node.nodeId);
        that.collection.remove(node.model);

        output.prepend('<p>' + node.text + ' was unchecked</p>');
        console.log("that.collection: ", that.collection);
      },
      onNodeSelected: function(event, node) {
        checkableTableOfIdeas.treeview('checkNode', node.nodeId);
      },
      onNodeUnselected: function(event, node) {
        checkableTableOfIdeas.treeview('uncheckNode', node.nodeId);
      },
      checkedIcon: "icon icon-check",
      uncheckedIcon: "icon icon-check-empty",
      expandIcon: "icon icon-arrowright", // we could use "icon icon-add" instead
      collapseIcon: "icon icon-arrowdown",
      emptyIcon: "indent"
    });

    this.$el.append(checkableTree);
    this.$el.append(output);
    
  }

});

module.exports = IdeaSelectorField;
