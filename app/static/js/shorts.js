// JS for shorts

const deleteShortModal = $('#delete-short-modal')

// Handle Shorts FORM Submit
$('#shortsForm').on('submit', function (event) {
    console.log('#shortsForm on submit', event)
    event.preventDefault()
    const form = $(this)
    // TODO: Simplify JSON Creation...
    let data = new FormData(this)
    data.forEach((value, key) => (data[key] = value))
    $.ajax({
        type: form.attr('method'),
        url: form.attr('action'),
        data: JSON.stringify(data),
        headers: { 'X-CSRFToken': csrftoken },
        success: function (data) {
            console.log('data:', data)
            alert(`Short Created: ${data.url}`)
            location.reload()
        },
        error: function (jqXHR) {
            if (jqXHR.status === 400) {
                const message = `${jqXHR.status}: ${jqXHR.responseJSON.error}`
                show_toast(message, 'danger', '6000')
            } else {
                const message = `${jqXHR.status}: ${jqXHR.statusText}`
                show_toast(message, 'danger', '6000')
            }
        },
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
    console.log(hookID)
    $.ajax({
        type: 'POST',
        url: `/ajax/delete/short/${hookID}/`,
        headers: { 'X-CSRFToken': csrftoken },
        success: function (data) {
            console.log('data:', data)
            deleteShortModal.modal('hide')
            console.log(`removing #short-${hookID}`)
            let count = $('#shorts-table tr').length
            $('#short-${hookID}').remove()
            if (count <= 2) {
                console.log('removing #shorts-table@ #shorts-table')
                $('#shorts-table').remove()
            }
            let message = `Short URL ${hookID} Successfully Removed.`
            show_toast(message, 'success')
        },
        error: function (jqXHR) {
            deleteShortModal.modal('hide')
            const message = `${jqXHR.status}: ${jqXHR.statusText}`
            show_toast(message, 'danger', '6000')
        },
    })
})
