// JS for shorts

const deleteShortModal = $('#delete-short-modal')
let shortsDataTable

// Handle Shorts FORM Submit
$('#shortsForm').on('submit', function (event) {
    console.log('#shortsForm submit', event)
    event.preventDefault()
    const form = $(this)
    console.log('form:', form)
    const data = new FormData(this)
    data.forEach((value, key) => (data[key] = value))
    $.ajax({
        type: form.attr('method'),
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

// Define Hook Modal and Delete handlers
// TODO: Use a proper selector
let hookID
$('.delete-short-btn').on('click', function () {
    hookID = $(this).data('hook-id')
    console.log(hookID)
    deleteShortModal.modal('show')
})

// Handle delete click confirmations
$('#short-delete-confirm').on('click', function () {
    console.log(`#short-delete-confirm click hookID: ${hookID}`)
    $.ajax({
        type: 'POST',
        url: `/ajax/delete/short/${hookID}/`,
        headers: { 'X-CSRFToken': csrftoken },
        success: function (data) {
            console.log('data:', data)
            deleteShortModal.modal('hide')
            console.log(`removing #short-${hookID}`)
            $(`#short-${hookID}`).remove()
            const count = $('#shorts-table tr').length
            if (count <= 1) {
                console.log('removing #shorts-table@ #shorts-table')
                $('#shorts-table').remove()
            }
            const message = `Short URL ${hookID} Successfully Removed.`
            show_toast(message, 'success')
        },
        error: function (jqXHR) {
            deleteShortModal.modal('hide')
            messageErrorHandler(jqXHR)
        },
        cache: false,
        contentType: false,
        processData: false,
    })
})

document.addEventListener('DOMContentLoaded', function () {
    shortsDataTable = $('#shorts-table').DataTable({
        order: [],
        processing: true,
        responsive: {
            details: false,
        },
        saveState: true,
        pageLength: -1,
        lengthMenu: [
            [10, 25, 50, 100, -1],
            [10, 25, 50, 100, 'All'],
        ],
        scrollX: false,
        columnDefs: [
            { targets: [0], responsivePriority: 1 },
            { targets: [1], responsivePriority: 2 },
            { targets: [2, 3, 4], responsivePriority: 3 },
        ],
    })
    shortsDataTable?.columns.adjust().draw()
})
