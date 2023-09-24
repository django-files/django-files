$(document).ready(function () {
    // Get and set the csrf_token
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value

    // Monitor websockets for new data and update results
    socket.addEventListener('message', (event) => {
        console.log('user.js socket.addEventListener message function')
        let data = JSON.parse(event.data)
        console.log(data)
        if (data.event === 'file-new') {
            $.get(`/ajax/files/tdata/${data.pk}`, function (response) {
                let message = `New File Upload: ${data.pk}`
                show_toast(message, 'success', '10000')
                let table = $('#files-table')
                if (table.length) {
                    $('#files-table tbody').prepend(response)
                    console.log(`Table Updated: ${data.pk}`)
                    $(`#file-${data.pk} .ctx-delete-btn`).click(deleteFileClick)
                }
            })
        } else if (data.event === 'file-delete') {
            let message = `File Deleted: ${data.pk}`
            show_toast(message, 'success', '10000')
            let table = $('#files-table')
            if (table.length) {
                let count = $('#files-table tr').length
                $(`#file-${data.pk}`).remove()
                if (count <= 2) {
                    console.log('removing #files-table@ #files-table')
                    table.remove()
                }
            }
        }
    })

    // Init the logout form click function
    $('.log-out').on('click', function () {
        $('#log-out').submit()
        return false
    })

    // Init the flush-cache click function
    $('#flush-cache').click(function () {
        console.log('flush-cache clicked...')
        $.ajax({
            url: '/flush-cache/',
            type: 'POST',
            headers: { 'X-CSRFToken': csrftoken },
            success: function (response) {
                console.log('response: ' + response)
                alert('Cache Flush Successfully Sent...')
                location.reload()
            },
            error: function (jqXHR) {
                console.log('jqXHR.status: ' + jqXHR.status)
                console.log('jqXHR.statusText: ' + jqXHR.statusText)
                let message = jqXHR.status + ': ' + jqXHR.statusText
                show_toast(message, 'danger', '6000')
            },
        })
        return false
    })
})

// Delete Click Handler
function deleteFileClick() {
    const pk = $(this).data('pk')
    console.log(`.ctx-delete-btn: pk: ${pk}`)
    $('#confirmDeleteFileBtn').data('pk', pk)
    $('#deleteFileModal').modal('show')
}
