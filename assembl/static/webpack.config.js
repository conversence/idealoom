var path = require('path'),
    glob = require('glob'),
    webpack = require('webpack'),
    _ = require('underscore'),
    ExtractTextPlugin = require("extract-text-webpack-plugin");

function theme_entries() {
  var entries = {},
      paths = glob.sync('./css/themes/**/*_web.scss'),
      i, path, parts, name;
  for (i = 0; i < paths.length; i++) {
    path = paths[i];
    parts = path.split('/');
    name = 'theme_' + parts[parts.length - 2] + '_web';
    entries[name] = path;
  }
  paths = glob.sync('./css/themes/**/*_notifications.scss');
  for (i = 0; i < paths.length; i++) {
    path = paths[i];
    parts = path.split('/');
    name = 'theme_' + parts[parts.length - 2] + '_notifications';
    entries[name] = path;
  }
  return entries;
}

module.exports = {
  entry: _.extend(theme_entries(), {
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
  }),
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
        loader: ExtractTextPlugin.extract(
          'style-loader', 'css-loader!sass-loader?includePaths[]=' + path.resolve(__dirname, 'node_modules/bourbon/app/assets/stylesheets')),
      },
      {
        test: /\.css$/,
        loader: ExtractTextPlugin.extract('style-loader', 'css-loader'),
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
      new ExtractTextPlugin("[name].css"),
  ],
};

