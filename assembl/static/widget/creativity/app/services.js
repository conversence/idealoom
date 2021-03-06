"use strict";

var creativityServices = angular.module('creativityServices', ['ngResource']);

creativityServices.service('AssemblToolsService', ['$window', '$rootScope', '$log', function($window, $rootScope, $log) {
  this.resourceToUrl = function(str) {
    var start = "local:";
    if (str && str.indexOf(start) == 0) {
      str = "/data/" + str.slice(start.length);
    }

    return str;
  };
}]);

creativityServices.service('WidgetService', ['$window', '$rootScope', '$log', '$http', function($window, $rootScope, $log, $http) {

  this.putJson = function(endpoint, post_data, result_holder) {
    console.log("putJson()");

    $http({
      method: 'PUT',
      url: endpoint,
      data: post_data,

      headers: {'Content-Type': 'application/json'}
    }).success(function(data, status, headers) {
      console.log("success");
      if (result_holder)
          result_holder.text("Success!");
      console.log("data:");
      console.log(data);
      console.log("status:");
      console.log(status);
      console.log("headers:");
      console.log(headers);
    }).error(function(status, headers) {
      console.log("error");
      if (result_holder)
          result_holder.text("Error");
    });
  };

}]);

creativityServices.factory('globalConfig', function($http) {

  var api_rest = 'test/config_test.json';

  return {
    fetch: function() {
      return $http.get(api_rest);
    }
  }

});

//CONFIG
creativityServices.factory('configTestingService', [function() {
  return {
    init: function() {

    },
    testCall: function() {
      $http({
        url: 'http://localhost:6543/data/Conversation/1/widgets',
        method: 'POST',
        data: {
          "@type": 'MultiCriterionVotingWidget',
          settings: {"idea": "local:GenericIdeaNode/2"}
        }}).then(function success(response) {
          getConfig(response.getResponseHeader('location'));
        },
        function error(response) {
          console.log(response);
        });

      function getConfig(value) {
        var widget = value.split(':');
        console.log('http://localhost:6543/data/' + widget[1]);
      }
    },
    getConfiguration: function(url, fnSuccess, fnError) {
      fnSuccess = fnSuccess || function(data) {
        console.log("data:");
        console.log(data);
      };
      fnError = fnError || function(jqXHR, textStatus, errorThrown) {
            };
      $http({
        url: url,
        method: 'GET',
        data: {}}).then(fnSuccess, fnError);
    }
  }

}]);

//CARD inspire me: send an idea to assembl
creativityServices.factory('sendIdeaService', ['$resource', function($resource) {
  return $resource('http://localhost:6543/api/v1/discussion/:discussionId/posts')
}]);

// WIP: use Angular's REST and Custom Services as our Model for Messages
creativityServices.factory('Discussion', ['$resource', function($resource) {
  return $resource('http://localhost:6543/data/Conversation/:discussionId', {}, {
    query: {method: 'GET', params: {discussionId: '1'}, isArray: false}
  });
}]);
