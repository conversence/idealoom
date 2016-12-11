var path = require('path'),
    glob = require('glob'),
    webpack = require('webpack'),
    _ = require('underscore'),
    ExtractTextPlugin = require("extract-text-webpack-plugin"),
    base_config = require('./webpack.config.js');

base_config.entry.main = [
  'webpack-dev-server/client?http://localhost:'+process.env.WEBPACK_PORT,
  'webpack/hot/only-dev-server',
  './js/app/index.js',
];

module.exports = _.extend(base_config, {
  devServer: {
    hot: true,
    inline: true,
    headers: {
        "Access-Control-Allow-Origin": process.env.ASSEMBL_URL,
        "Access-Control-Allow-Credentials":true
    },
    port: process.env.WEBPACK_PORT,
    host: "0.0.0.0",
  },
  plugins: [
      new webpack.HotModuleReplacementPlugin(),
      new webpack.ResolverPlugin(
        new webpack.ResolverPlugin.DirectoryDescriptionFilePlugin('../../bower.json', ['main'])
      ),
      new webpack.optimize.CommonsChunkPlugin({
        names: ['infrastructure', 'manifest'] // Specify the common bundle's name.
      }),
      new ExtractTextPlugin("[name].css"),
  ],
  sassLoader: {
    data: '$static_url: "~/";',
  },
});
