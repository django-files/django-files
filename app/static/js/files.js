$(document).ready(function () {
    // Get and set the csrf_token
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value

    // Define Hook Modal and Delete handlers
    let deleteFileModal
    try {
        deleteFileModal = new bootstrap.Modal('#deleteFileModal', {})
    } catch (error) {
        console.log('#deleteFileModal Not Found')
    }
    let hookID
    $('.delete-file-btn').click(function () {
        hookID = $(this).data('hook-id')
        console.log(hookID)
        deleteFileModal.show()
    })

    // Handle delete click confirmations
    $('#confirmDeleteFileBtn').click(function () {
        console.log(hookID)
        $.ajax({
            url: `/ajax/delete/file/${hookID}/`,
            type: 'POST',
            headers: { 'X-CSRFToken': csrftoken },
            success: function (data) {
                console.log('data: ' + data)
                deleteFileModal.hide()
                console.log('removing #file-' + hookID)
                let count = $('#files-table tr').length
                $('#file-' + hookID).remove()
                if (count <= 2) {
                    console.log('removing #files-table@ #files-table')
                    $('#files-table').remove()
                }
                let message = 'File ' + hookID + ' Successfully Removed.'
                show_toast(message, 'success')
            },
            error: function (jqXHR) {
                console.log('jqXHR.status: ' + jqXHR.status)
                console.log('jqXHR.statusText: ' + jqXHR.statusText)
                deleteFileModal.hide()
                let message = jqXHR.status + ': ' + jqXHR.statusText
                show_toast(message, 'danger', '10000')
            },
        })
    })

    $('#user').change(function () {
        let user = $(this).val()
        console.log('user: ' + user)
        if (user) {
            let url = new URL(location.href)
            url.searchParams.set('user', user)
            location.href = url.toString()
        }
    })
})
