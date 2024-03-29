// JS for Site Settings

const deleteDiscordHookModal = $('#deleteDiscordHookModal')

// TODO: Use a proper selector
let hookID
$('.deleteDiscordHookBtn').on('click', function (event) {
    console.log('.deleteDiscordHookBtn click', event)
    hookID = $(this).data('hook-id')
    console.log(hookID)
    deleteDiscordHookModal.modal('show')
})

// Handle Confirm Delete Clicks
$('#confirmDeleteDiscordHookBtn').on('click', function (event) {
    console.log('#confirmDeleteDiscordHookBtn click', event)
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
            messageErrorHandler(jqXHR)
        },
        cache: false,
        contentType: false,
        processData: false,
    })
})

// Handle profile save button click and response
$('#settingsForm').on('submit', function (event) {
    console.log('#settingsForm submit', event)
    event.preventDefault()
    const form = $(this)
    console.log('form:', form)
    $.ajax({
        type: form.attr('method'),
        url: window.location.pathname,
        data: new FormData(this),
        headers: { 'X-CSRFToken': csrftoken },
        success: function (data) {
            console.log('data:', data)
            if (data.reload) {
                alert('Settings changed require reload...')
                location.reload()
            } else {
                let message = 'Settings Saved Successfully.'
                show_toast(message, 'success')
            }
        },
        error: function (jqXHR) {
            formErrorHandler.call(this, form, jqXHR)
        },
        cache: false,
        contentType: false,
        processData: false,
    })
})

// Handle Invites Form
$('#invitesForm').on('submit', function (event) {
    console.log('#invitesForm submit', event)
    event.preventDefault()
    const form = $(this)
    console.log('form:', form)
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
        error: messageErrorHandler,
        cache: false,
        contentType: false,
        processData: false,
    })
})

// Handle Update Checks
$('#check-for-update').on('click', function (event) {
    console.log('#check-for-update click', event)
    const data = JSON.stringify({ method: 'check-for-update' })
    console.log('data:', data)
    socket.send(data)
})
