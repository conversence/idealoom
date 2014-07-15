define(function(require){
    'use strict';

    var Base = require('models/base'),
           _ = require('underscore');
    /**
     * @class IdeaModel
     */
    var IdeaLinkModel = Base.Model.extend({

        /**
         * @init
         */
        initialize: function(obj){
            obj = obj || {};
            var that = this;
        },

        /**
         * Defaults
         */
        defaults: {
            source: '',
            target: '',
            order: 1
        },

        correctParentBug: function() {
            var child = assembl.ideaList.ideas.get(this.get('target'));
            if (child.get('parentId') === null) {
                console.log("correct parent bug");
                child.set('parentId', this.get('source'));
                child.get('parents').push(this.get('source'));
            }
        }

    });

    /**
     * @class IdeaColleciton
     */
    var IdeaLinkCollection = Base.Collection.extend({

        /**
         * The model
         * @type {IdeaModel}
         */
        model: IdeaLinkModel,

        /**
         * add function
         * @type {IdeaModel}
         */
        add: function(models, options) {
            models = Backbone.Collection.prototype.set.call(this, models, options);
            if (_.isArray(models)) {
                _.each(models, function(m) {m.correctParentBug();})
            } else {
                models.correctParentBug();
            }
            return models;
        }
    });

    return {
        Model: IdeaLinkModel,
        Collection: IdeaLinkCollection
    };

});
