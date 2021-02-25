const { extendDefaultPlugins } = require('svgo');
module.exports = {
  plugins: extendDefaultPlugins([
    {
      name: 'cleanupIDs',
      active: false
    }
  ])
};
