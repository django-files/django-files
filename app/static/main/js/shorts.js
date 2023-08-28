$(document).ready(function () {
    // Get and set the csrf_token
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value

    // Handle Shorts FORM Submit
    $('#shorts-form').on('submit', function (event) {
        event.preventDefault()
        let data = new FormData($(this)[0])

        data.forEach((value, key) => (data[key] = value))
        // let json = JSON.stringify(formData);

        $.ajax({
            // url: window.location.pathname,
            url: $('#shorts-form').attr('action'),
            type: 'POST',
            headers: { 'X-CSRFToken': csrftoken },
            // data: formData,
            data: JSON.stringify(data),
            beforeSend: function (jqXHR) {
                //
            },
            success: function (data, textStatus, jqXHR) {
                console.log(
                    'Status: ' +
                        jqXHR.status +
                        ', Data: ' +
                        JSON.stringify(data)
                )
                alert('Short Created: ' + data['url'])
                location.reload()
                // let message = 'Short Created: ' + data['url'];
                // show_toast(message,'success', '6000');
            },
            complete: function (data, textStatus) {
                //
            },
            error: function (data, status, error) {
                console.log(
                    'Status: ' +
                        data.status +
                        ', Response: ' +
                        data.responseText
                )
                // TODO: Replace this with real error handling
                let message = data.status + ': ' + data.responseJSON['error']
                show_toast(message, 'danger', '6000')
            },
            cache: false,
            contentType: false,
            processData: false,
        })
    })

        // Define Hook Modal and Delete handlers
        const deleteHookModal = new bootstrap.Modal('#delete-short-modal', {})
        let hookID
        $('.delete-short-btn').click(function () {
            hookID = $(this).data('hook-id')
            console.log(hookID)
            deleteHookModal.show()
        })

        // Handle delete click confirmations
        $('#confirm-delete-hook-btn').click(function () {
            if ($('#confirm-delete-hook-btn').hasClass('disabled')) {
                return
            }
            console.log(hookID)
            $.ajax({
                type: 'POST',
                url: `/ajax/delete/short/${hookID}/`,
                headers: { 'X-CSRFToken': csrftoken },
                beforeSend: function () {
                    console.log('beforeSend')
                    $('#confirm-delete-hook-btn').addClass('disabled')
                },
                success: function (response) {
                    console.log('response: ' + response)
                    deleteHookModal.hide()
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
                error: function (xhr, status, error) {
                    console.log('xhr status: ' + xhr.status)
                    console.log('status: ' + status)
                    console.log('error: ' + error)
                    deleteHookModal.hide()
                    let message = xhr.status + ': ' + error
                    show_toast(message, 'danger', '15000')
                },
                complete: function () {
                    console.log('complete')
                    $('#confirm-delete-hook-btn').removeClass('disabled')
                },
            })
        })
})
