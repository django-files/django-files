// rollup.config.js
import resolve from '@rollup/plugin-node-resolve'
import commonjs from '@rollup/plugin-commonjs'

export default {
    input: 'node_modules/qr-code-styling/lib/qr-code-styling.js',
    output: {
        file: 'app/static/dist/qr-code-styling/qr-code-styling.js',
        format: 'umd',
        name: 'QRCodeStyling',
    },
    plugins: [resolve(), commonjs()],
}
