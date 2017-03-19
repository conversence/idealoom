/**
 * Resolve configuration before access to a controller
 * */
SessionApp.factory('IdeaService', ['$resource', function($resource) {

  return $resource('/data/GenericIdeaNode/:id/?view=creativity_widget', null, {

    'get': {
      method: 'GET', params: { id: '@id' },
      transformResponse: function(idea) {
        idea = angular.fromJson(idea);
        return idea;
      }
    }

  });
}]);
