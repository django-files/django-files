$(document).ready(function () {
    // Get and set the csrf_token
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value

    // Handle Shorts FORM Submit
    $('#shortsForm').on('submit', function (event) {
        console.log('#shortsForm on submit function')
        event.preventDefault()
        let form = $(this)
        console.log(form)
        // TODO: Simplify JSON Creation...
        let data = new FormData(form[0])
        data.forEach((value, key) => (data[key] = value))
        $.ajax({
            type: form.attr('method'),
            url: form.attr('action'),
            data: JSON.stringify(data),
            headers: { 'X-CSRFToken': csrftoken },
            success: function (data) {
                console.log('data: ' + JSON.stringify(data))
                alert('Short Created: ' + data['url'])
                location.reload()
            },
            error: function (jqXHR) {
                console.log('jqXHR.status: ' + jqXHR.status)
                console.log('jqXHR.statusText: ' + jqXHR.statusText)
                // TODO: Replace this with real error handling
                if (jqXHR.status === 400) {
                    show_toast(jqXHR.responseJSON['error'], 'danger', '6000')
                } else {
                    let message = jqXHR.status + ': ' + jqXHR.statusText
                    show_toast(message, 'danger', '6000')
                }
            },
            cache: false,
            contentType: false,
            processData: false,
        })
    })

    // // Define Hook Modal and Delete handlers
    let deleteShortModal
    try {
        deleteShortModal = new bootstrap.Modal('#delete-short-modal', {})
    } catch (error) {
        console.log('#delete-short-modal Not Found')
    }
    let hookID
    $('.delete-short-btn').click(function () {
        hookID = $(this).data('hook-id')
        console.log(hookID)
        deleteShortModal.show()
    })

    // Handle delete click confirmations
    $('#short-delete-confirm').click(function () {
        console.log(hookID)
        $.ajax({
            type: 'POST',
            url: `/ajax/delete/short/${hookID}/`,
            headers: { 'X-CSRFToken': csrftoken },
            success: function (data) {
                console.log('data: ' + data)
                deleteShortModal.hide()
                console.log('removing #short-' + hookID)
                let count = $('#shorts-table tr').length
                $('#short-' + hookID).remove()
                if (count <= 2) {
                    console.log('removing #shorts-table@ #shorts-table')
                    $('#shorts-table').remove()
                }
                let message = 'Short URL ' + hookID + ' Successfully Removed.'
                show_toast(message, 'success')
            },
            error: function (jqXHR) {
                console.log('jqXHR.status: ' + jqXHR.status)
                console.log('jqXHR.statusText: ' + jqXHR.statusText)
                deleteShortModal.hide()
                let message = jqXHR.status + ': ' + jqXHR.statusText
                show_toast(message, 'danger', '6000')
            },
        })
    })
})
