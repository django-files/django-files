// JS for Home Page

import { initFilesTable, addFileTableRows } from './file-table.js'

import { fetchFiles } from './api-fetch.js'

let filesDataTable

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
    filesDataTable = initFilesTable(false, false, false)
    let files = await fetchFiles(1, 10)
    if (files.files.length >= 10) {
        $('.files-truncation-warning').show()
    }
    addFileTableRows(await fetchFiles(1, 10))
    filesDataTable.on('select', function (e, dt, type, indexes) {
        document.getElementById('bulk-actions').disabled = false
    })
    filesDataTable.on('deselect', function (e, dt, type, indexes) {
        if (filesDataTable.rows({ selected: true }).count() === 0) {
            document.getElementById('bulk-actions').disabled = true
        }
    })
    filesDataTable?.columns.adjust().draw()
}
