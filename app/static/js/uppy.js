import {
    Uppy,
    Dashboard,
    DropTarget,
    Webcam,
    Audio,
    ScreenCapture,
    XHRUpload,
} from '/static/uppy/uppy.min.js'

console.debug('LOADING: uppy.js')
console.debug('uploadUrl:', uploadUrl)

const fileUploadModal = $('#fileUploadModal')
// if (typeof fileUploadModal === 'undefined') {
//     fileUploadModal
// }

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
    .use(DropTarget, {
        target: document.body,
    })

uppy.on('file-added', (file) => {
    console.debug('file-added:', file)
    fileUploadModal.modal('show')
})

uppy.on('upload-success', (fileCount) => {
    console.debug('upload-success:', fileCount)
    if (typeof fileUploadModal !== 'undefined') {
        fileUploadModal?.modal('hide')
    }
})

uppy.on('upload-error', (file, error, response) => {
    console.debug('upload-error:', response.body.message)
})

uppy.on('error', (error) => {
    console.debug('error:', error)
})

fileUploadModal?.on('hidden.bs.modal', (event) => {
    console.debug('hidden.bs.modal:', event)
    uppy.cancelAll()
})
