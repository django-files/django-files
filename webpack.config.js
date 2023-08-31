const path = require('path')
// const CopyWebpackPlugin = require('copy-webpack-plugin')

module.exports = {
    entry: {
        'uppy.min': './entry.js',
    },
    output: {
        filename: '[name].js',
        path: path.resolve(__dirname, 'app/static/dist/uppy'),
    },
}
