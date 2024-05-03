import {
    Uppy,
    Dashboard,
    Webcam,
    Audio,
    ScreenCapture,
    XHRUpload,
} from '/static/uppy/uppy.min.js'

console.debug('LOADING: uppy.js')
console.debug('uploadUrl:', uploadUrl)

function getResponseError(responseText, response) {
    return new Error(JSON.parse(responseText).message)
}

const uppy = new Uppy({ debug: true, autoProceed: false })
    .use(Dashboard, {
        inline: true,
        theme: 'auto',
        target: '#uppy',
        showProgressDetails: true,
        showLinkToFileUploadResult: true,
        autoOpenFileEditor: true,
        proudlyDisplayPoweredByUppy: false,
        note: 'Django Files Upload',
        height: 380,
        width: '100%',
        metaFields: [
            { id: 'name', name: 'Name', placeholder: 'File Name' },
            {
                id: 'Expires-At',
                name: 'Expires At',
                placeholder: 'File Expiration Time.',
            },
            {
                id: 'info',
                name: 'Info',
                placeholder: 'Information about the file.',
            },
        ],
        browserBackButtonClose: false,
    })
    .use(Webcam, { target: Dashboard })
    .use(Audio, { target: Dashboard })
    .use(ScreenCapture, { target: Dashboard })
    .use(XHRUpload, {
        endpoint: uploadUrl,
        headers: {
            'X-CSRFToken': $('input[name=csrfmiddlewaretoken]').val(),
        },
        getResponseError: getResponseError,
    })

uppy.on('upload-success', (fileCount) => {
    console.debug('upload-success:', fileCount)
    fileUploadModal?.modal('hide')
})

uppy.on('upload-error', (file, error, response) => {
    console.debug('upload-error:', response.body.message)
})

fileUploadModal?.on('hidden.bs.modal', (event) => {
    console.debug('hidden.bs.modal:', event)
    uppy.cancelAll()
})
