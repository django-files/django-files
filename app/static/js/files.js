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
                console.log('data: ' + data)
                $('#deleteFileModal').modal('hide')
                console.log(`removing #file-${pk}`)
                let count = $('#files-table tr').length
                $(`#file-${pk}`).remove()
                if (count <= 2) {
                    console.log('removing #files-table@ #files-table')
                    $('#files-table').remove()
                }
                let message = `File ${pk} Successfully Removed.`
                show_toast(message, 'success')
            },
            error: function (jqXHR) {
                console.log('jqXHR.status: ' + jqXHR.status)
                console.log('jqXHR.statusText: ' + jqXHR.statusText)
                $('#deleteFileModal').modal('hide')
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
