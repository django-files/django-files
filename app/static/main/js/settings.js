$(document).ready(function () {
    // Get and set the csrf_token
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value

    // Define Delete Modal and Delete Button class handler
    const deleteHookModal = new bootstrap.Modal('#delete-hook-modal', {})
    let hookID
    $('.delete-webhook-btn').click(function () {
        hookID = $(this).data('hook-id')
        console.log(hookID)
        deleteHookModal.show()
    })

    // Handle Confirm Delete Clicks id handler
    $('#confirm-delete-hook-btn').click(function () {
        if ($('#confirm-delete-hook-btn').hasClass('disabled')) {
            return
        }
        console.log(hookID)
        $.ajax({
            type: 'POST',
            url: `/ajax/delete/hook/${hookID}/`,
            headers: { 'X-CSRFToken': csrftoken },
            beforeSend: function () {
                console.log('beforeSend')
                $('#confirm-delete-hook-btn').addClass('disabled')
            },
            success: function (response) {
                console.log('response: ' + response)
                deleteHookModal.hide()
                console.log('removing #wehook-' + hookID)
                let count = $('#webhooks-table tr').length
                $('#webhook-' + hookID).remove()
                if (count <= 2) {
                    console.log('removing #webhooks-table@ #webhooks')
                    $('#webhooks-table').remove()
                }
                let message = 'Webhoook ' + hookID + ' Successfully Removed.'
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

    // Remove .is-invalid when clicking on a filed
    $('.form-control').focus(function () {
        $(this).removeClass('is-invalid')
    })

    // Handle profile save button click and response
    $('#settings-form').on('submit', function (event) {
        event.preventDefault()
        if ($('#submit-app-btn').hasClass('disabled')) {
            return
        }
        var formData = new FormData($(this)[0])
        $.ajax({
            url: window.location.pathname,
            // url: $('#settings-form').attr('action'),
            type: 'POST',
            headers: { 'X-CSRFToken': csrftoken },
            data: formData,
            beforeSend: function (jqXHR) {
                $('#save-settings').addClass('disabled')
            },
            success: function (data, textStatus, jqXHR) {
                console.log(
                    'Status: ' +
                        jqXHR.status +
                        ', Data: ' +
                        JSON.stringify(data)
                )
                if (data['reload']) {
                    alert(
                        'Settings changed require reload to take effect.\n' +
                            'The page will now refresh...'
                    )
                } else {
                    let message = 'Settings Saved Successfully.'
                    show_toast(message, 'success', '6000')
                }
                // $("#message-success").show();
            },
            complete: function (data, textStatus) {
                $('#save-settings').removeClass('disabled')
                console.log(data.responseJSON)
                if (data.responseJSON['reload']) {
                    location.reload()
                }
            },
            error: function (data, status, error) {
                console.log(
                    'Status: ' +
                        data.status +
                        ', Response: ' +
                        data.responseText
                )
                let message = data.status + ': ' + error
                show_toast(message, 'danger', '6000')
                try {
                    console.log(data.responseJSON)
                    if (data.responseJSON.hasOwnProperty('error_message')) {
                        alert(data.responseJSON['error_message'])
                    } else {
                        $($('#settings-form').prop('elements')).each(
                            function () {
                                if (
                                    data.responseJSON.hasOwnProperty(this.name)
                                ) {
                                    $('#' + this.name + '-invalid')
                                        .empty()
                                        .append(data.responseJSON[this.name])
                                    $(this).addClass('is-invalid')
                                }
                            }
                        )
                    }
                } catch (error) {
                    console.log(error)
                    alert('Fatal Error: ' + error)
                }
            },
            cache: false,
            contentType: false,
            processData: false,
        })
    })
})
