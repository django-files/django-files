$(document).ready(function () {
    // Get and set the csrf_token
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value

    $('.delete-file-btn').click(function () {
        let pk = $(this).data('pk')
        console.log(`Delete Button: pk: ${pk}`)
        $('#confirmDeleteFileBtn').data('pk', pk)
        $('#deleteFileModal').modal('show')
    })

    // Handle delete click confirmations
    $('#confirmDeleteFileBtn').click(function () {
        let pk = $(this).data('pk')
        console.log(`Confirm Delete: pk: ${pk}`)
        $.ajax({
            url: `/ajax/delete/file/${pk}/`,
            type: 'POST',
            headers: { 'X-CSRFToken': csrftoken },
            success: function (data) {
                console.log(`File ${pk} Deleted. Websocket Processing.`)
            },
            error: function (jqXHR) {
                let message = jqXHR.status + ': ' + jqXHR.statusText
                show_toast(message, 'danger', '10000')
            },
            complete: function () {
                $('#deleteFileModal').modal('hide')
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
