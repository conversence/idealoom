/**
 * 
 * @module app.views.segmentList
 */

import Marionette from 'backbone.marionette';

import Backbone from 'backbone';
import BackboneModal from 'backbone.modal';
import _ from 'underscore';
import $ from 'jquery';
import highlight from 'jquery-highlight';
import IdeaLoom from '../app.js';
import Ctx from '../common/context.js';
import Segment from '../models/segment.js';
import Types from '../utils/types.js';
import i18n from '../utils/i18n.js';
import Permissions from '../utils/permissions.js';
import CollectionManager from '../common/collectionManager.js';
import PanelSpecTypes from '../utils/panelSpecTypes.js';
import BasePanel from './basePanel.js';
import AgentViews from './agent.js';
import BackboneSubset from 'Backbone.Subset';
import Promise from 'bluebird';

class SegmentView extends Marionette.View.extend({
  template: '#tmpl-segment',
  gridSize: BasePanel.prototype.CLIPBOARD_GRID_SIZE,

  ui: {
    postItFooter: '.postit-footer .text-quotation',
    postIt: '.postit',
    authorAvatar: '.js_authorAvatar',
    authorName: '.js_authorName'
  },

  regions: {
    authorAvatar: '@ui.authorAvatar',
    authorName: '@ui.authorName'
  },

  events: {
    'click .js_closeExtract': 'onCloseButtonClick',
    'click .segment-link': "onSegmentLinkClick",
    'click .js_selectAsNugget': 'selectAsNugget',
    'dragstart .bx.postit': 'onDragStart', // when the user starts dragging this extract
    'dragend .bx.postit': 'onDragEnd' // when the user starts dragging this extract
  }
}) {
  initialize(options) {
    this.allUsersCollection = options.allUsersCollection;
    this.allMessagesCollection = options.allMessagesCollection;
    this.closeDeletes = options.closeDeletes;
    this.postCreator = undefined;
  }

  serializeData() {
    var post;
    var idPost = this.model.get('idPost');
    var currentUser = Ctx.getCurrentUser();
    var harvester = this.model.getCreatorFromUsersCollection(this.allUsersCollection);

    if (!harvester) {
      throw new Error("No harvester found in segment");
    }

    if (idPost) {
      post = this.allMessagesCollection.get(idPost);
      if (post) {
        this.postCreator = this.allUsersCollection.get(post.get('idCreator'));
      }
    }

    return {
      segment: this.model,
      post: post,
      contentCreator: this.postCreator,
      harvester: harvester,
      allUsersCollection: this.allUsersCollection,
      canEditExtracts: currentUser.can(Permissions.EDIT_EXTRACT),
      canAddExtracts: currentUser.can(Permissions.ADD_EXTRACT),
      i18n,
      ctx: Ctx
    }
  }

  onRender() {
    Ctx.initTooltips(this.$el);
    Ctx.convertUrlsToLinks(this.ui.postItFooter);

    this.renderAuthor();
    if (!_.isUndefined(this.model.get('firstInlist'))) {
      this.$el.attr('id', 'tour_step_segment');
      IdeaLoom.tour_vent.trigger("requestTour", "segment");
    }
  }

  renderAuthor() {
    var agentAvatarView;
    var agentNameView;

    if (this.postCreator) {
      agentAvatarView = new AgentViews.AgentAvatarView({
        model: this.postCreator
      });
      this.showChildView('authorAvatar', agentAvatarView);
      agentNameView = new AgentViews.AgentNameView({
        model: this.postCreator
      });
      this.showChildView('authorName', agentNameView);
    }
  }

  // when the user starts dragging this extract
  onDragStart(ev) {
    ev.currentTarget.style.opacity = 0.4;

    var cid = ev.currentTarget.getAttribute('data-segmentid');
    var segment = this.model.collection.get(cid);

    Ctx.showDragbox(ev, segment.getQuote());
    Ctx.setDraggedSegment(segment);
  }

  // "The dragend event is fired when a drag operation is being ended (by releasing a mouse button or hitting the escape key)." quote https://developer.mozilla.org/en-US/docs/Web/Events/dragend
  onDragEnd(ev) {
    //console.log("SegmentView::onDragEnd()", ev);
    ev.currentTarget.style.opacity = 1;
  }

  onSegmentLinkClick(ev) {
    var cid = ev.currentTarget.getAttribute('data-segmentid');
    var collectionManager = new CollectionManager();

    collectionManager.getAllExtractsCollectionPromise()
            .then(function(allExtractsCollection) {
              var segment = allExtractsCollection.get(cid);
              Ctx.showTargetBySegment(segment);
            });
  }

  onCloseButtonClick(ev) {
    var cid = ev.currentTarget.getAttribute('data-segmentid');
    if (this.closeDeletes) {
      this.model.destroy({
        success: function(model, resp) {
                },
        error: function(model, resp) {
          console.error('ERROR: onCloseButtonClick', resp);
        }
      });
    } else {
      this.model.save('idIdea', null, {
        success: function(model, resp) {
                },
        error: function(model, resp) {
          console.error('ERROR: onCloseButtonClick', resp);
        }
      });
    }
  }

  selectAsNugget(e) {
    e.preventDefault();
    var that = this;

    if (!this.model.get('important')) {
      this.model.set('important', true);
    } else {
      this.model.set('important', false);
    }

    this.model.save(null, {
      success: function(model, resp) {
        if (model.get('important')) {
          that.$('.nugget-indice .nugget').addClass('isSelected');
        } else {
          that.$('.nugget-indice .nugget').removeClass('isSelected');
        }
      },
      error: function(model, resp) {
        console.error('ERROR: selectAsNugget', resp);
      }
    });
  }
}

class SegmentListView extends Marionette.CollectionView.extend({
  childView: SegmentView
}) {
  initialize(options) {

    if (this.collection.name == "IdeaSegmentList" && this.collection.models.length) {
      var firstelm = this.collection.models[0];
      firstelm.attributes.firstInlist = true;
    }

    this.childViewOptions = {
      allUsersCollection: options.allUsersCollection,
      allMessagesCollection: options.allMessagesCollection,
      closeDeletes: options.closeDeletes
    };
  }
}

class Clipboard extends Backbone.Subset.extend({
  name: 'Clipboard',
  liveupdate_keys: ['idIdea']
}) {
  beforeInitialize(models, options) {
    this.currentUserId = options.currentUserId;
  }

  sieve(extract) {
    return extract.get('idIdea') == null;
  }

  comparator(e1, e2) {
    var currentUserId = this.currentUserId;
    var myE1 = e1.get('idCreator') == currentUserId;
    var myE2 = e2.get('idCreator') == currentUserId;
    if (myE1 != myE2) {
      return myE1 ? -1 : 1;
    }

    return e2.getCreatedTime() - e1.getCreatedTime();
  }
}

class IdeaSegmentListSubset extends Backbone.Subset.extend({
  name: 'IdeaSegmentList',
  liveupdate_keys: ['idIdea']
}) {
  beforeInitialize(models, options) {
    this.ideaId = options.ideaId;
  }

  sieve(extract) {
    return extract.get('idIdea') == this.ideaId;
  }

  comparator(segment) {
    return -segment.getCreatedTime();
  }
}

class SegmentListPanel extends BasePanel.extend({
  template: '#tmpl-segmentList',
  panelType: PanelSpecTypes.CLIPBOARD,
  className: 'clipboard',
  minWidth: 270,

  ui: {
    panelBody:'.panel-body',
    clipboardCount: ".clipboardCount",
    postIt: '.postitlist',
    clearSegmentList:'#segmentList-clear',
    closeButton:'#segmentList-closeButton',
    bookmark:'.js_bookmark'
  },

  regions: {
    extractList: '.postitlist'
  },

  events: {
    'dragenter @ui.postIt': 'onDragEnter', // when the user is dragging something from anywhere and moving the mouse towards this panel
    'dragend @ui.postIt': "onDragEnd",
    'dragover @ui.panelBody': 'onDragOver',
    'dragleave @ui.panelBody': 'onDragLeave',
    'drop @ui.panelBody': 'onDrop',

    'click @ui.clearSegmentList': "onClearButtonClick",
    'click @ui.closeButton': "closePanel",
    'click @ui.bookmark': 'onBookmark'
  }
}) {
  initialize(options) {
    super.initialize(...arguments);
    var that = this;
    var collectionManager = new CollectionManager();

    collectionManager.getAllExtractsCollectionPromise()
            .then(function(allExtractsCollection) {
              if(!that.isDestroyed()) {
                that.clipboard = new Clipboard([], {
                  parent: allExtractsCollection,
                  currentUserId: Ctx.getCurrentUser().id
                });
                that.listenTo(allExtractsCollection, 'invalid', function(model, error) {
                  alert(error);
                });

                that.listenTo(that.clipboard, 'add', function(segment) {
                  that.highlightSegment(segment);
                });
                that.listenTo(that.clipboard, 'add remove reset change', that.resetTitle);
                window.setTimeout(function() {
                  that.render();
                }, 0);
              }
            });

    // TODO: There is no trigger for this event. See if there should be one.
    this.listenTo(IdeaLoom.other_vent, 'segmentListPanel:showSegment', function(segment) {
      that.showSegment(segment);
    });
  }

  getTitle() {
    return i18n.gettext('Clipboard');
  }

  serializeData() {
    return {
      Ctx
    }
  }

  onBeforeRender() {
    Ctx.removeCurrentlyDisplayedTooltips(this.$el);
  }

  onRender() {
    var that = this;
    var collectionManager = new CollectionManager();
    if (Ctx.debugRender) {
      console.log("segmentListPanel:onRender() is firing");
    }

    if (this.clipboard) {
      Ctx.initTooltips(this.$el);

      Promise.join(collectionManager.getAllExtractsCollectionPromise(),
                   collectionManager.getAllUsersCollectionPromise(),
                   collectionManager.getAllMessageStructureCollectionPromise(),
                function(allExtractsCollection, allUsersCollection, allMessagesCollection) {

                  var segmentListView = new SegmentListView({
                    collection: that.clipboard,
                    allUsersCollection: allUsersCollection,
                    allMessagesCollection: allMessagesCollection,
                    closeDeletes: true
                  });

                  that.showChildView('extractList', segmentListView);
                });
    }

    this.resetTitle();
  }

  resetTitle() {
    if (this.clipboard) {
      var numExtracts = this.clipboard.models.length;
      this.ui.clipboardCount.html("(" + numExtracts + ")");
      this.getPanelWrapper().resetTitle("<i class='icon-clipboard'></i> " + i18n.gettext('Clipboard') + " (" + numExtracts + ")");
    } else {
      this.ui.clipboardCount.html("");
      this.getPanelWrapper().resetTitle(i18n.gettext('Clipboard') + " (" + i18n.gettext('empty') + ")");
    }
  }

  /**
   * Add a segment to the clipboard.  If the segment exists, it will be
   * unlinked from it's idea (if any).
   * @param {Segment} segment
   */
  addSegment(segment) {
    var collectionManager = new CollectionManager();

    collectionManager.getAllExtractsCollectionPromise()
            .then(function(allExtractsCollection) {
              delete segment.attributes.highlights;

              allExtractsCollection.add(segment, {merge: true});
              segment.save('idIdea', null);
            });
  }

  /**
   * Creates a segment with the given text and adds it to the segmentList
   * @param  {string} text
   * @param  {string} post - The origin post (nullable)
   * @returns {Segment}
   */
  addTextAsSegment(text, post) {
    var idPost = null;

    if (post) {
      idPost = post.getId();
    }

    var segment = new Segment.Model({
      target: { "@id": idPost, "@type": Types.EMAIL },
      text: text,
      quote: text,
      idCreator: Ctx.getCurrentUser().getId(),
      idPost: idPost
    });

    if (segment.isValid()) {
      this.addSegment(segment);

      segment.save(null, {
        success: function(model, resp) {
                },
        error: function(model, resp) {
          console.error('ERROR: addTextAsSegment', resp);
        }
      });
    }
  }

  /**
   * Shows the given segment
   * @param {Segment} segment
   */
  showSegment(segment) {
    //TODO: add a new behavior for this (popin...)
    this.highlightSegment(segment);
  }

  /**
   * Highlight the given segment with an small fx
   * @param {Segment} segment
   */
  highlightSegment(segment) {
    var selector = Ctx.format('.box[data-segmentid={0}]', segment.cid);
    var box = this.$(selector);

    if (box.length) {
      var panelBody = this.$('.panel-body');
      var panelOffset = panelBody.offset().top;
      var offset = box.offset().top;

      // Scrolling to the element
      var target = offset - panelOffset + panelBody.scrollTop();
      panelBody.animate({ scrollTop: target });
      box.highlight();
    }
  }

  // "The dragend event is fired when a drag operation is being ended (by releasing a mouse button or hitting the escape key)." quote https://developer.mozilla.org/en-US/docs/Web/Events/dragend
  onDragEnd(ev) {
    //console.log("segmentListPanel::onDragEnd()", ev);

    Ctx.setDraggedSegment(null);
    this.$el.removeClass('is-dragover');
  }

  // The dragenter event is fired when the mouse enters a drop target while dragging something
  // We have to define dragenter and dragover event listeners which both call ev.preventDefault() in order to be sure that subsequent drop event will fire => http://stackoverflow.com/questions/21339924/drop-event-not-firing-in-chrome
  // "Calling the preventDefault method during both a dragenter and dragover event will indicate that a drop is allowed at that location." quote https://developer.mozilla.org/en-US/docs/Web/Guide/HTML/Drag_operations#droptargets
  onDragEnter(ev) {
    //console.log("segmentListPanel::onDragEnter() ev: ", ev);
    if (ev) {
      ev.preventDefault();
    }
  }

  // The dragover event is fired when an element or text selection is being dragged over a valid drop target (every few hundred milliseconds).
  // We have to define dragenter and dragover event listeners which both call ev.preventDefault() in order to be sure that subsequent drop event will fire => http://stackoverflow.com/questions/21339924/drop-event-not-firing-in-chrome
  // "Calling the preventDefault method during both a dragenter and dragover event will indicate that a drop is allowed at that location." quote https://developer.mozilla.org/en-US/docs/Web/Guide/HTML/Drag_operations#droptargets
  onDragOver(ev) {
    //console.log("segmentListPanel::onDragOver()");
    if (ev) {
      ev.preventDefault();
    }

    if ( ev && "originalEvent" in ev ) {
      ev = ev.originalEvent;
    }

    // /!\ See comment at the top of the onDrop() method
    if ( ev && "dataTransfer" in ev ) {
      ev.dataTransfer.dropEffect = 'move';
      ev.dataTransfer.effectAllowed = 'move';
    }

    var isText = false;
    if (ev.dataTransfer && ev.dataTransfer.types && _.indexOf(ev.dataTransfer.types, "text/plain") > -1) {
      isText = Ctx.draggedIdea ? false : true;
    }

    if (Ctx.getDraggedSegment() !== null || isText) {
      this.$el.addClass("is-dragover");
    }

    if (Ctx.getDraggedAnnotation() !== null) {
      this.$el.addClass("is-dragover");
    }
  }

  // "Finally, the dragleave event will fire at an element when the drag leaves the element. This is the time when you should remove any insertion markers or highlighting. You do not need to cancel this event. [...] The dragleave event will always fire, even if the drag is cancelled, so you can always ensure that any insertion point cleanup can be done during this event." quote https://developer.mozilla.org/en-US/docs/Web/Guide/HTML/Drag_operations
  onDragLeave(ev) {
    //console.log("segmentListPanel::onDragLeave()");

    this.$el.removeClass('is-dragover');
  }

  // /!\ The browser will not fire the drop event if, at the end of the last call of the dragenter or dragover event listener (right before the user releases the mouse button), one of these conditions is met:
  // * one of ev.dataTransfer.dropEffect or ev.dataTransfer.effectAllowed is "none"
  // * ev.dataTransfer.dropEffect is not one of the values allowed in ev.dataTransfer.effectAllowed
  // "If you don't change the effectAllowed property, then any operation is allowed, just like with the 'all' value. So you don't need to adjust this property unless you want to exclude specific types." quote https://developer.mozilla.org/en-US/docs/Web/Guide/HTML/Drag_operations
  // "During a drag operation, a listener for the dragenter or dragover events can check the effectAllowed property to see which operations are permitted. A related property, dropEffect, should be set within one of these events to specify which single operation should be performed. Valid values for the dropEffect are none, copy, move, or link." quote https://developer.mozilla.org/en-US/docs/Web/API/DataTransfer
  // ev.preventDefault() is also needed here in order to prevent default action (open as link for some elements)
  onDrop(ev) {
    //console.log("segmentListPanel::onDrop()");

    if (ev) {
      ev.preventDefault();
    }

    this.$el.removeClass('is-dragover');

    var idea = Ctx.popDraggedIdea();
    if (idea) {
      return; // Do nothing
    }

    var segment = Ctx.getDraggedSegment();
    if (segment) {
      this.addSegment(segment);
      Ctx.setDraggedSegment(null);
    }

    var annotation = Ctx.getDraggedAnnotation();
    if (annotation) {
      Ctx.saveCurrentAnnotationAsExtract();
    }

    //the segments is already created
    /*var text = ev.dataTransfer.getData("Text");
    if (text) {
        this.addTextAsSegment(text);
    }*/
    
    this.render();

    return;
  }

  onClearButtonClick(ev) {
    var that = this;
    var collectionManager = new CollectionManager();
    var ok = confirm(i18n.gettext('Are you sure you want to empty your entire clipboard?'));
    var user_id = Ctx.getCurrentUser().id;

    if (ok) {
      collectionManager.getAllExtractsCollectionPromise()
                .done(function() {
                  that.clipboard.filter(function(s) {
                    return s.get('idCreator') == user_id
                  }).map(function(segment) {

                    segment.destroy({
                      success: function(model, resp) {
                            },
                      error: function(model, resp) {
                        console.error('ERROR: onClearButtonClick', resp)
                      }
                    });
                  });
                });
    }
  }

  onBookmark(e) {
    e.preventDefault();

    class Modal extends Backbone.Modal.extend({
      template: _.template($('#tmpl-bookmarket').html()),
      className: 'capture generic-modal popin-wrapper',
      cancelEl: '.close, .btn-primary'
    }) {}

    IdeaLoom.rootView.showChildView('slider', new Modal());
  }
}

export default {
  Clipboard: Clipboard,
  IdeaSegmentListSubset: IdeaSegmentListSubset,
  SegmentView: SegmentView,
  SegmentListView: SegmentListView,
  SegmentListPanel: SegmentListPanel
};
