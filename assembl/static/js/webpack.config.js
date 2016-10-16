var path = require('path');
var webpack = require('webpack');

module.exports = {
  entry: {
    main: './app/index.js'
  },
  output: {
    path: './build',
    filename: './app.js',
    // filename: '[name].bundle.js',
    publicPath: '/static/js/build/',
  },
  resolve: {
    modulesDirectories: [
      'node_modules',
      __dirname + '/bower',
      __dirname + '/app',
      __dirname + '/lib',
    ],
  },
  plugins: [
      new webpack.ResolverPlugin(
          new webpack.ResolverPlugin.DirectoryDescriptionFilePlugin('.bower.json', ['main'])
      ),
  ],
};
