process.env.sassStaticUrl = '~/';

var path = require('path'),
    glob = require('glob'),
    webpack = require('webpack'),
    _ = require('underscore'),
    ExtractTextPlugin = require("extract-text-webpack-plugin"),
    base_config = require('./webpack.config.js'),
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
    inline: false,
    headers: {
        "Access-Control-Allow-Origin": process.env.ASSEMBL_URL,
        "Access-Control-Allow-Credentials": "true"
    },
    port: webpack_port,
    host: webpackHost,
    disableHostCheck: disableHostCheck,
  },
  plugins: [
      new webpack.HotModuleReplacementPlugin(),
      new webpack.optimize.CommonsChunkPlugin({
        names: ['infrastructure', 'manifest'] // Specify the common bundle's name.
      }),
      new ExtractTextPlugin('[name].css'),
      new DashboardPlugin(),
  ],
});
