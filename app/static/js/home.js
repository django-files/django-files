// JS for Home Page

import { initFilesTable, addFileTableNodes } from './file-table.js'

import { fetchFiles } from './api-fetch.js'

document.addEventListener('DOMContentLoaded', initHome)

$('#quick-short-form').on('submit', function (event) {
    console.log('#quick-short-form submit', event)
    event.preventDefault()
    const form = $(this)
    console.log('form:', form)
    const data = { url: $('#long-url').val() }
    $.ajax({
        type: 'POST',
        url: form.attr('action'),
        data: JSON.stringify(data),
        headers: { 'X-CSRFToken': csrftoken },
        success: function (data) {
            console.log('data:', data)
            form.trigger('reset')
            alert(`Short Created: ${data.url}`)
            location.reload()
        },
        error: messageErrorHandler,
        cache: false,
        contentType: false,
        processData: false,
    })
})

async function initHome() {
    filesDataTable = initFilesTable()
    addFileTableNodes(await fetchFiles(1, 10))
}
