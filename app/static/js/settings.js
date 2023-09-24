$(document).ready(function () {
    // Get and set the csrf_token
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value

    // Define Delete Modal and Delete Button class handler
    let deleteDiscordHookModal
    try {
        deleteDiscordHookModal = new bootstrap.Modal(
            '#deleteDiscordHookModal',
            {}
        )
    } catch (error) {
        console.log('#deleteDiscordHookModal Not Found')
    }
    // TODO: Use a proper selector and NOT a hookID scoped variable
    let hookID
    $('.deleteDiscordHookBtn').click(function () {
        hookID = $(this).data('hook-id')
        console.log(hookID)
        deleteDiscordHookModal.show()
    })

    // Handle Confirm Delete Clicks
    $('#confirmDeleteDiscordHookBtn').click(function () {
        console.log(hookID)
        $.ajax({
            type: 'POST',
            url: `/ajax/delete/hook/${hookID}/`,
            headers: { 'X-CSRFToken': csrftoken },
            success: function (data) {
                console.log('data: ' + data)
                deleteDiscordHookModal.hide()
                console.log(`removing #wehook-${hookID}`)
                let count = $('#discordWebhooksTable tr').length
                $(`#webhook-${hookID}`).remove()
                if (count <= 2) {
                    console.log('removing #discordWebhooksTable@')
                    $('#discordWebhooksTable').remove()
                }
                let message = `Webhoook ${hookID} Successfully Removed.`
                show_toast(message, 'success')
            },
            error: function (jqXHR) {
                console.log('jqXHR.status: ' + jqXHR.status)
                console.log('jqXHR.statusText: ' + jqXHR.statusText)
                deleteDiscordHookModal.hide()
                let message = 'Error: ' + jqXHR.statusText
                show_toast(message, 'danger', '10000')
            },
        })
    })

    // Handle profile save button click and response
    $('#settingsForm').on('submit', function (event) {
        console.log('#settingsForm on submit function')
        event.preventDefault()
        let form = $(this)
        console.log(form)
        $.ajax({
            url: window.location.pathname,
            type: form.attr('method'),
            data: new FormData(form[0]),
            headers: { 'X-CSRFToken': csrftoken },
            success: function (data) {
                console.log('data: ' + JSON.stringify(data))
                if (data['reload']) {
                    alert(
                        'Settings changed require reload to take effect.\n' +
                            'The page will now refresh...'
                    )
                    location.reload()
                } else {
                    let message = 'Settings Saved Successfully.'
                    show_toast(message, 'success', '6000')
                }
            },
            error: function (jqXHR) {
                console.log('jqXHR.status: ' + jqXHR.status)
                console.log('jqXHR.statusText: ' + jqXHR.statusText)
                show_toast(jqXHR.statusText, 'danger', '6000')
                if (jqXHR.status === 400) {
                    let data = jqXHR.responseJSON
                    console.log(data)
                    $(form.prop('elements')).each(function () {
                        if (data.hasOwnProperty(this.name)) {
                            $('#' + this.name + '-invalid')
                                .empty()
                                .append(data[this.name])
                            $(this).addClass('is-invalid')
                        }
                    })
                } else {
                    alert(jqXHR.statusText)
                }
            },
            cache: false,
            contentType: false,
            processData: false,
        })
    })

    // Handle Invites Form
    $('#invitesForm').on('submit', function (event) {
        console.log('#invitesForm on submit function')
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
                alert('Invite Created: ' + data['invite'])
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
})
