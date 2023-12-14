// JS for Site Settings

const deleteDiscordHookModal = $('#deleteDiscordHookModal')

// TODO: Use a proper selector
let hookID
$('.deleteDiscordHookBtn').on('click', function () {
    console.log('.deleteDiscordHookBtn on click', event)
    hookID = $(this).data('hook-id')
    console.log(hookID)
    deleteDiscordHookModal.modal('show')
})

// Handle Confirm Delete Clicks
$('#confirmDeleteDiscordHookBtn').on('click', function (event) {
    console.log('#confirmDeleteDiscordHookBtn on click', event)
    console.log(`hookID: ${hookID}`)
    $.ajax({
        type: 'POST',
        url: `/ajax/delete/hook/${hookID}/`,
        headers: { 'X-CSRFToken': csrftoken },
        success: function (data) {
            console.log('data:', data)
            deleteDiscordHookModal.modal('hide')
            console.log(`removing #wehook-${hookID}`)
            const count = $('#discordWebhooksTable tr').length
            $(`#webhook-${hookID}`).remove()
            if (count <= 2) {
                console.log('removing #discordWebhooksTable@')
                $('#discordWebhooksTable').remove()
            }
            const message = `Webhoook ${hookID} Successfully Removed.`
            show_toast(message, 'success')
        },
        error: function (jqXHR) {
            deleteDiscordHookModal.modal('hide')
            const message = `${jqXHR.status}: ${jqXHR.statusText}`
            show_toast(message, 'danger', '10000')
        },
    })
})

// Handle profile save button click and response
$('#settingsForm').on('submit', function (event) {
    console.log('#settingsForm on submit', event)
    event.preventDefault()
    let form = $(this)
    console.log(form)
    $.ajax({
        url: window.location.pathname,
        type: form.attr('method'),
        data: new FormData(this),
        headers: { 'X-CSRFToken': csrftoken },
        success: function (data) {
            console.log('data:', data)
            if (data.reload) {
                alert(
                    'Settings changed require reload to take effect.\nThe page will now refresh...'
                )
                location.reload()
            } else {
                let message = 'Settings Saved Successfully.'
                show_toast(message, 'success', '6000')
            }
        },
        error: function (jqXHR) {
            if (jqXHR.status === 400) {
                form400handler.call(this, form, jqXHR)
            }
            const message = `${jqXHR.status}: ${jqXHR.statusText}`
            show_toast(message, 'danger', '6000')
        },
        cache: false,
        contentType: false,
        processData: false,
    })
})

// Handle Invites Form
$('#invitesForm').on('submit', function (event) {
    console.log('#invitesForm on submit', event)
    event.preventDefault()
    const form = $(this)
    console.log(form)
    // TODO: Simplify JSON Creation...
    const data = new FormData(this)
    data.forEach((value, key) => (data[key] = value))
    $.ajax({
        type: form.attr('method'),
        url: form.attr('action'),
        data: JSON.stringify(data),
        headers: { 'X-CSRFToken': csrftoken },
        success: function (data) {
            console.log('data:', data)
            alert(`Invite Created: ${data.invite}`)
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

// Handle Update Checks
$('#check-for-update').on('click', function (event) {
    console.log('#check-for-update')
    const data = JSON.stringify({ method: 'check-for-update' })
    console.log('data:', data)
    socket.send(data)
})
