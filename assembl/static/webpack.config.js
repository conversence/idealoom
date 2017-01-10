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
    main: './js/app/index.js',
    infrastructure: [
      'jquery',
      'underscore',
      'backbone',
      'backbone.babysitter',
      'backbone.marionette',
      'backbone.modal',
      'backbone-model-file-upload',
      'backbone.radio',
      'backbone.modal',
      'bootstrap-notify',
      'bluebird',
      'ckeditor',
      'd3',
      'd3-array',
      'd3-axis',
      'd3-interpolate',
      'd3-scale',
      'd3-selection',
      'd3-format',
      'd3-time',
      'hopscotch',
      'hopscotch',
      'jed',
      'linkifyjs',
      'moment',
      'raven-js',
      'sockjs-client',

      // Those choke because they expect jquery in namespace.
      // 'jquery.dotdotdot',
      // 'annotator/annotator-full.js',
      // 'Backbone.Subset',
      // 'bootstrap-dropdown',
      // 'bootstrap-tooltip',
      // 'jquery-highlight/jquery.highlight.js',
      // 'jquery-oembed-all/jquery.oembed',
      // 'jquery-autosize',
    ],
    testInfra: [
      'mocha',
    ],
    tests: [
      'chai',
      'chai-as-promised',
      'lolex',
      'sinon',
      './js/app/tests.js',
    ],
  }),
  output: {
    path: path.join(__dirname, 'js/build'),
    filename: '[name].js',
    publicPath: '/js/build/',
  },
  resolve: {
    modulesDirectories: [
      __dirname + '/node_modules',
      __dirname + '/js/bower',
      __dirname + '/js/app',
      __dirname + '/js/lib',
    ],
    alias: {
      sinon: 'sinon/pkg/sinon',
      bourbon: 'bourbon/app/assets/stylesheets/_bourbon.scss',
      'jquery.dotdotdot': 'jquery.dotdotdot/src/js/jquery.dotdotdot.js',
      'jquery-highlight': 'jquery-highlight/jquery.highlight.js',
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
        test: /\.(jpg|png|woff|woff2|eot|ttf|svg|html)$/,
        loader: 'url-loader',
      },
      {
        test: /LICENSE$/,
        loader: 'url-loader',
      },
    ],
    noParse: [/sinon/],
  },
  node: {
    fs: "empty",
    child_process: "empty",
  },
  plugins: [
      // this makes mocha choke on requiring supports-color for very obscure reasons.
      // Revisit.
      // new webpack.DefinePlugin({
      //   'process.env': {
      //     NODE_ENV: JSON.stringify('production')
      //   }
      // }),
      new webpack.ResolverPlugin(
        new webpack.ResolverPlugin.DirectoryDescriptionFilePlugin('../../bower.json', ['main'])
      ),
      new webpack.optimize.CommonsChunkPlugin({
        names: ['infrastructure', 'manifest'] // Specify the common bundle's name.
      }),
      new ExtractTextPlugin("[name].css"),
  ],
  sassLoader: {
    data: '$static_url: "~/static/";',
  }
};
