// JS for Home Page

import {
    initFilesTable,
    addFileTableRows,
    showTableSkeletons,
} from './file-table.js'

import { fetchFiles } from './api-fetch.js'
import { socket } from './socket.js'

const MAX_HOME_FILES = 10

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
    // Enable ordering so the sort by ID desc is applied — new socket rows go to
    // the top automatically via the shared file-table.js socket handler.
    filesDataTable = initFilesTable(false, true, false)
    showTableSkeletons(MAX_HOME_FILES)
    // Fetch one extra to detect whether more files exist without a second request.
    const files = await fetchFiles(1, MAX_HOME_FILES + 1)
    const hasMore = files.files?.length > MAX_HOME_FILES
    if (hasMore) {
        files.files = files.files.slice(0, MAX_HOME_FILES)
        document
            .querySelector('.files-truncation-warning')
            .classList.remove('d-none')
    }
    addFileTableRows(files)
    filesDataTable.on('select', function (_e, _dt, _type, _indexes) {
        document.getElementById('bulk-actions').disabled = false
    })
    filesDataTable.on('deselect', function (_e, _dt, _type, _indexes) {
        if (filesDataTable.rows({ selected: true }).count() === 0) {
            document.getElementById('bulk-actions').disabled = true
        }
    })
    filesDataTable?.columns.adjust().draw()
}

// file-table.js registers its socket listener at import time, so it fires first:
// it adds the new row and redraws with ordering (newest ID at top). This listener
// then trims any overflow back to MAX_HOME_FILES.
socket?.addEventListener('message', function (event) {
    if (event.data === 'pong') return
    const data = JSON.parse(event.data)
    if (data.event !== 'file-new' || !filesDataTable) return
    const count = filesDataTable.rows().count()
    if (count > MAX_HOME_FILES) {
        const lastIdx = filesDataTable.rows({ order: 'applied' }).indexes()[
            MAX_HOME_FILES
        ]
        if (lastIdx !== undefined) {
            filesDataTable.row(lastIdx).remove().draw(false)
        }
    }
    document
        .querySelector('.files-truncation-warning')
        .classList.remove('d-none')
})
