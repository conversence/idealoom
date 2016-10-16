var path = require('path');
var webpack = require('webpack');

module.exports = {
  entry: {
    app: './js/app/index.js',
    infrastructure: [
      'jquery',
      'underscore',
      'backbone',
      'backbone.marionette',
      'backbone-modal',
      'Backbone.Subset',
      'backbone-model-file-upload',
      'sockjs-client',
      'jquery.dotdotdot',
      'jquery-oembed-all/jquery.oembed',
      'bootstrap-growl/jquery.bootstrap-growl',
      'jquery-highlight/jquery.highlight.js',
      'hopscotch',
      'bootstrap-tooltip',
      'bootstrap-dropdown',
      'annotator/annotator-full.js',
    ],
    tests: [
      './js/app/tests.js',
      'mocha',
      'chai',
      'chai-as-promised',
      'lolex',
      'sinon',
    ],
    assembl_web_css: [
      './node_modules/hopscotch/dist/css/hopscotch.css',
      './css/themes/default/assembl_web.scss',
    ],
    assembl_notifications_css: [
      './css/themes/default/assembl_notifications.scss',
    ],
  },
  output: {
    path: './js/build',
    filename: '[name].js',
    publicPath: '/static/js/build/',
  },
  resolve: {
    modulesDirectories: [
      'node_modules',
      __dirname + '/js/bower',
      __dirname + '/js/app',
      __dirname + '/js/lib',
    ],
    alias: {
      sinon: 'sinon/pkg/sinon',
      bourbon: __dirname + '/node_modules/bourbon/app/assets/stylesheets/_bourbon.scss',
    },
  },
  module: {
    loaders: [
      {
        test: /\.json$/,
        loader: 'json',
      },
      {
        test: /sinon.*\.js$/,
        loader: 'imports?require=>false,define=>false',
      },
      {
        test: /\.scss$/,
        loaders: ["style", "css", 'sass?includePaths[]='+ path.resolve(__dirname, 'node_modules/bourbon/app/assets/stylesheets')]
      },
      {
        test: /\.css$/,
        loaders: ["style", "css"]
      },
      {
        test: /\.(jpg|png|woff|woff2|eot|ttf|svg)$/,
        loader: 'url-loader',
      },
    ],
    noParse: [/sinon/],
  },
  plugins: [
      new webpack.ResolverPlugin(
          new webpack.ResolverPlugin.DirectoryDescriptionFilePlugin('.bower.json', ['main'])
      ),
  ],
};
