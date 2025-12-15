const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  // Use environment variable or default to port 8000 (v4 API)
  const apiTarget = process.env.REACT_APP_API_URL || 'http://localhost:8000';
  
  app.use(
    '/api',
    createProxyMiddleware({
      target: apiTarget,
      changeOrigin: true,
      logLevel: 'debug',
    }),
  );
};
