var path = require('path'),
    glob = require('glob'),
    webpack = require('webpack'),
    _ = require('underscore'),
    MiniCssExtractPlugin = require("mini-css-extract-plugin"),
    HtmlWebpackPlugin = require('html-webpack-plugin'),
    HtmlWebpackHarddiskPlugin = require('html-webpack-harddisk-plugin'),
    TerserPlugin = require('terser-webpack-plugin'),
    sassStaticUrl = process.env.sassStaticUrl || '/static/';

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
//     infrastructure: [
//       'jquery',
//       'underscore',
//       'backbone',
//       'backbone.marionette',
//       'backbone.modal',
//       'backbone-model-file-upload',
//       'backbone.radio',
//       'bootstrap-notify',
//       'bluebird',
//       'ckeditor',
//       'd3',
//       'd3-array',
//       'd3-axis',
//       'd3-interpolate',
//       'd3-scale',
//       'd3-selection',
//       'd3-format',
//       'd3-time',
//       'hopscotch',
//       'jed',
//       'linkifyjs',
//       'moment',
//       'raven-js',
//       'sockjs-client',
// 
//       // Those choke because they expect jquery in namespace.
//       'jquery.dotdotdot',
//       // 'annotator/annotator-full.js',
//       // 'Backbone.Subset',
//       'bootstrap-dropdown',
//       'bootstrap-tooltip',
//       'jquery-highlight/jquery.highlight.js',
//       'jquery-oembed-all/jquery.oembed',
//       'jquery-autosize',
//     ],
//     testInfra: [
//       'mocha',
//       'chai',
//       'chai-as-promised',
//       'lolex',
//       'sinon',
//     ],
    tests: [
      './js/app/tests.js',
    ],
    annotator_ext: './css/lib/annotator_ext.scss',
  }),
  optimization: {
    minimizer: [
      new TerserPlugin({
        sourceMap: true,
        parallel: true,
        cache: true
    })],
  },
  output: {
    path: path.join(__dirname, 'js/build'),
    filename: (chunkData) => {
      return chunkData.chunk.name === 'annotator_ext' ? '[name].js': '[name].[hash].js';
    },
    sourceMapFilename: "[name].[hash].js.map",
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
        test: /\.pegjs$/,
        use: [{
          loader: 'pegjs-loader',
        }],
      },
      {
        test: /bootstrap.*\.js|jquery[-\.]/,
        use: [
          {
            loader: 'imports-loader',
            options: {
                type: "commonjs",
                imports: {
                    moduleName: 'jquery',
                    name: 'jQuery',
                }
            },
          },
        ],
      },
      {
        test: /\/js\/app\/.*\.js$|chai-as-promised|d3-array/,
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
        use: [
          MiniCssExtractPlugin.loader,
          'css-loader',
          {
            loader: 'sass-loader',
            options: {
              sassOptions: {
                includePaths: [
                  path.resolve(__dirname, 'node_modules/bourbon/app/assets/stylesheets'),
                ],
              },
              additionalData: '$static_url: "'+sassStaticUrl+'";',
            },
          },
        ],
      },
      {
        test: /\.css$/,
        use: [
          MiniCssExtractPlugin.loader,
          'css-loader',
        ]
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
  optimization: {
    // splitChunks: {
    //   chunks: "all",
    //   cacheGroups: {
    //     infrastructure: {
    //       test: "infrastructure",
    //       name: "infrastructure",
    //       priority: -40,
    //       enforce: true
    //     },
    //     testInfra: {
    //       test: "testInfra",
    //       name: "testInfra",
    //       priority: -30,
    //       enforce: true
    //     },
    //     main: {
    //       test: "main",
    //       name: "main",
    //       priority: -20,
    //       enforce: true
    //     },
    //     tests: {
    //       test: "tests",
    //       name: "tests",
    //       priority: -10,
    //       enforce: true
    //     },
    //   }
    // }
  },
  plugins: [
    // this makes mocha choke on requiring supports-color for very obscure reasons.
    // Revisit.
    // new webpack.DefinePlugin({
    //   'process.env': {
    //     NODE_ENV: JSON.stringify('production')
    //   }
    // }),
    // temporary: No caching because it breaks annotator_ext. Wait for
    // https://github.com/webpack-contrib/mini-css-extract-plugin/pull/225
    new MiniCssExtractPlugin({
      filename: '[name].css'
    }),
    new HtmlWebpackPlugin({
      alwaysWriteToDisk: true,
      filename: 'index.html',
      excludeChunks: ['tests', 'annotator_ext'],
    }),
    new HtmlWebpackPlugin({
      alwaysWriteToDisk: true,
      filename: 'test.html',
      excludeChunks: ['main', 'annotator_ext'],
    }),
    new HtmlWebpackHarddiskPlugin(),
  ],
};
