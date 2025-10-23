const path = require('path');

module.exports = {
  mode: 'development',
  entry: './src/index.js',
  devServer: {
    port: 3000,
    host: '0.0.0.0',
    allowedHosts: 'all',
    static: {
      directory: path.join(__dirname, 'public'),
    },
  },
};
