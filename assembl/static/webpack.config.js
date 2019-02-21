var path = require('path'),
    glob = require('glob'),
    webpack = require('webpack'),
    _ = require('underscore'),
    UglifyJSPlugin = require('uglifyjs-webpack-plugin'),
    sassStaticUrl = process.env.sassStaticUrl || '~/static/',
    ExtractTextPlugin = require('extract-text-webpack-plugin');

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
      'backbone.marionette',
      'backbone.modal',
      'backbone-model-file-upload',
      'backbone.radio',
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
      'jed',
      'linkifyjs',
      'moment',
      'raven-js',
      'sockjs-client',

      // Those choke because they expect jquery in namespace.
      'jquery.dotdotdot',
      // 'annotator/annotator-full.js',
      // 'Backbone.Subset',
      'bootstrap-dropdown',
      'bootstrap-tooltip',
      'jquery-highlight/jquery.highlight.js',
      'jquery-oembed-all/jquery.oembed',
      'jquery-autosize',
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
    annotator_ext: './css/lib/annotator_ext.scss',
  }),
  output: {
    path: path.join(__dirname, 'js/build'),
    filename: '[name].js',
    sourceMapFilename: "[name].js.map",
    publicPath: '/js/build/',
  },
  resolve: {
    modules: [
      "node_modules",
      path.join(__dirname, 'js/bower'),
      path.join(__dirname, 'js/app'),
      path.join(__dirname, 'js/lib'),
    ],
    descriptionFiles: ['package.json', '../../bower.json'],
    alias: {
      sinon: path.resolve(__dirname, 'node_modules/sinon/pkg/sinon'),
      bourbon$: path.resolve(__dirname, 'node_modules/bourbon/app/assets/stylesheets/_bourbon.scss'),
      'jquery.dotdotdot$': path.resolve(__dirname, 'js/bower/jquery.dotdotdot/src/js/jquery.dotdotdot.js'),
      'jquery-highlight$': path.resolve(__dirname, 'js/lib/jquery-highlight/jquery.highlight.js'),
      'moment$': 'moment/moment',
    },
  },
  module: {
    rules: [
      {
        test: /\.json$/,
        use: [{
          loader: 'json-loader',
        }],
      },
      {
        test: /\.pegjs$/,
        use: [{
          loader: 'pegjs-loader',
        }],
      },
      {
        test: /sinon.*\.js$/,
        use: [
          {
            loader: 'imports-loader?define=>false',
          }],
      },
      {
        test: /bootstrap.*\.js|jquery[-\.]/,
        use: [
          {
            loader: 'imports-loader?jquery,jQuery=jquery',
          },
        ],
      },
      {
        test: /\/js\/app\/.*\.js$|chai-as-promised/,
        use: [{
            loader: 'babel-loader',
            options: {
                presets: ['@babel/preset-env'],
                cacheDirectory: false,
            },
        }],
      },
      {
        test: /\.scss$/,
        use: ExtractTextPlugin.extract({
          fallback: 'style-loader',
          use: [
            {
              loader: 'css-loader',
            },
            {
              loader: 'sass-loader',
              options: {
                includePaths: [
                  path.resolve(__dirname, 'node_modules/bourbon/app/assets/stylesheets'),
                ],
                data: '$static_url: "' + sassStaticUrl + '";',
              },
            },
          ],
        }),
      },
      {
        test: /\.css$/,
        use: ExtractTextPlugin.extract({
          fallback: 'style-loader',
          use: 'css-loader',
        }),
      },
      {
        test: /\.(jpg|png|woff|woff2|eot|ttf|svg|html)$/,
        use: [{
          loader: 'url-loader',
        }],
      },
      {
        test: /LICENSE$/,
        use: [{
          loader: 'url-loader',
        }],
      },
    ],
    noParse: [/sinon/],
  },
  node: {
    fs: 'empty',
    child_process: 'empty',
  },
  devtool: 'source-map',
  plugins: [
    // this makes mocha choke on requiring supports-color for very obscure reasons.
    // Revisit.
    // new webpack.DefinePlugin({
    //   'process.env': {
    //     NODE_ENV: JSON.stringify('production')
    //   }
    // }),
    new webpack.optimize.CommonsChunkPlugin({
      names: ['infrastructure', 'manifest'] // Specify the common bundle's name.
    }),
    new UglifyJSPlugin({ sourceMap: true }),
    new ExtractTextPlugin('[name].css'),
  ],
};
