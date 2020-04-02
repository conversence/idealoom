/**
 * 
 * @module app.views.visitors.firstIdeaToShowVisitor
 */

import Visitor from './visitor.js';

/** This visitor will find the first idea with extracts, and/or the first idea altogether.
*/
var FirstIdeaToShowVisitor = function(extractsCollection) {
  this.extractsCollection = extractsCollection;
};

FirstIdeaToShowVisitor.prototype = new Visitor();

FirstIdeaToShowVisitor.prototype.visit = function(idea) {
  const ideaId = idea.getId();
  if (this.ideaWithExtract !== undefined) {
    return false;
  }

  if (this.extractsCollection.find((extract) =>
        extract.get("important") || extract.linkedToIdea(ideaId))) {
    this.ideaWithExtract = idea;
    return false;
  }

  if (this.firstIdea === undefined && !idea.isRootIdea()) {
    this.firstIdea = idea;
  }

  return true;
};

export default FirstIdeaToShowVisitor;
