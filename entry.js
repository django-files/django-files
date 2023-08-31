import Uppy from '@uppy/core'
import Dashboard from '@uppy/dashboard'
import XHRUpload from '@uppy/xhr-upload'

const uppy = Uppy()
uppy.use(Dashboard, {})
uppy.use(XHRUpload, {})

// Export the uppy instance if needed
export default uppy
