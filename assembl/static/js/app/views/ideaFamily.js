/**
 * 
 * @module app.views.ideaFamily
 */

import Backbone from 'backbone';

import _ from 'underscore';
import Ctx from '../common/context.js';

class IdeaFamilyView extends Backbone.View.extend({
  /**
   * Tag name
   * @type {string}
   */
  tagName: 'div',

  /**
   * The class of view used inside the family
   */
  innerViewClass: null,

  /**
   * The class of view used inside the family
   */
  innerViewClassInitializeParams: {},

  /**
   * The template
   * @type {template}
   */
  template: Ctx.loadTemplate('ideaFamily')
}) {
  /**
   * @init
   */
  initialize(obj) {
    this.view_data = obj.view_data
    this.isOpen = true;
    this.innerViewClass = obj.innerViewClass;
    this.innerViewClassInitializeParams = obj.innerViewClassInitializeParams;
  }

  /**
   * The render
   * @returns {IdeaInSynthesisView}
   */
  render() {
    var that = this;
    var data = this.model.toJSON();
    var authors = [];
    var view_data = this.view_data;
    var render_data = view_data[this.model.getId()];
    var ideaView = new this.innerViewClass(_.extend({model: this.model}, this.innerViewClassInitializeParams));
    _.extend(data, render_data);
    Ctx.removeCurrentlyDisplayedTooltips(this.$el);

    this.$el.addClass('ideafamily-item');
    if (render_data['is_last_sibling']) {
      this.$el.addClass('is-last-sibling');
    }

    // if(!render_data['true_sibling']) {
    //     this.$el.addClass('false-sibling');
    // }

    if (render_data['children'].length > 0) {
      this.$el.addClass('has-children');
    } else {
      this.$el.addClass('no-children');
    }

    if (render_data['skip_parent']) {
      this.$el.addClass('skip_parent');
    }

    this.$el.addClass('level' + render_data['level']);

    if (this.isOpen === true) {
      this.$el.addClass('is-open');
    } else {
      this.$el.removeClass('is-open');
    }

    data.id = this.model.getId();

    this.$el.html(this.template(data));
    Ctx.initTooltips(this.$el);
    this.$el.find('>.ideafamily-body>.ideafamily-idea').append(ideaView.render().el);

    var rendered_children = [];
    _.each(render_data['children'], function(idea) {
      var ideaFamilyView = new IdeaFamilyView({
              model: idea,
              view_data: that.view_data,
              innerViewClass: that.innerViewClass,
              innerViewClassInitializeParams: that.innerViewClassInitializeParams});
      rendered_children.push(ideaFamilyView.render().el);
    });
    this.$el.find('>.ideafamily-body>.ideafamily-children').append(rendered_children);

    return this;
  }
}

export default IdeaFamilyView;
