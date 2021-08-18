process.env.sassStaticUrl = '/';

var path = require('path'),
    glob = require('glob'),
    webpack = require('webpack'),
    _ = require('underscore'),
    base_config = require('./webpack.config.js'),
    MiniCssExtractPlugin = require("mini-css-extract-plugin"),
    HtmlWebpackPlugin = require('html-webpack-plugin'),
    HtmlWebpackHarddiskPlugin = require('html-webpack-harddisk-plugin'),
    DashboardPlugin = require('webpack-dashboard/plugin'),
    webpackHost = process.env.WEBPACK_URL.split('://')[1].split(':')[0],
    webpack_port = parseInt(process.env.WEBPACK_URL.split(':')[2]),
    disableHostCheck = false;

if (true) {
  // allow access from outside
  webpackHost = "0.0.0.0";
  disableHostCheck = true;
}

base_config.entry.main = [
  'webpack-dev-server/client?' + process.env.WEBPACK_URL,
  'webpack/hot/only-dev-server',
  './js/app/index.js',
];

base_config.output.publicPath = process.env.WEBPACK_URL + '/js/build';

module.exports = _.extend(base_config, {
  devServer: {
    hot: true,
    headers: {
      "Access-Control-Allow-Origin": process.env.ASSEMBL_URL,
      "Access-Control-Allow-Credentials": "true"
    },
    port: webpack_port,
    host: webpackHost,
    allowedHosts: (disableHostCheck)?"all":webpackHost,
    static: {
      directory: '.'
    }
  },
  mode: 'development',
  optimization: {
    minimize: false
  },
  plugins: [
    base_config.plugins[0],
    base_config.plugins[1],
    new webpack.HotModuleReplacementPlugin(),
    new MiniCssExtractPlugin({ filename: "[name].[contenthash].css" }),
    new HtmlWebpackPlugin({
      alwaysWriteToDisk: true,
      filename: 'live_index.html',
      excludeChunks: ['tests'],
    }),
    new HtmlWebpackPlugin({
      alwaysWriteToDisk: true,
      filename: 'live_test.html',
    }),
    new HtmlWebpackHarddiskPlugin(),
    new DashboardPlugin(),
  ],
});

