// JS for Drag and Drop

// TODO: NOT USED - TO BE REMOVED

dropTarget?.addEventListener('dragenter', (event) => {
    // console.debug('dragenter', event)
    event.preventDefault()
})

dropTarget?.addEventListener('dragover', (event) => {
    // console.debug('dragover', event)
    event.preventDefault()
})

dropTarget?.addEventListener('drop', (event) => {
    console.debug('drop', event)
    const dataTransfer = event.dataTransfer
    event.preventDefault()
    console.debug('dataTransfer', dataTransfer)
    if (!dataTransfer.files?.length) {
        return console.debug('no files found in dragged item')
    }
    fileUploadModal.modal('show')
    uppy.addFile(dataTransfer.files[0])
})

// let counter = 0
// document.addEventListener('dragenter', (event) => {
//     event.preventDefault()
//     if (counter++ === 0) {
//         console.log('entered the page')
//         dropOverlay.classList.remove('d-none')
//     }
// })
// document.addEventListener('dragleave', (event) => {
//     event.preventDefault()
//     if (--counter === 0) {
//         console.log('left the page')
//         dropOverlay.classList.add('d-none')
//     }
// })
