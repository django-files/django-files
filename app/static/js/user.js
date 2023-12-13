// JS for Authenticated Users

// Get and set the csrf_token
const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value

socket?.addEventListener('message', function (event) {
    // console.log('socket: user.js:', event)
    let data = JSON.parse(event.data)
    if (data.event === 'file-new') {
        let message = `New File Upload: ${data.pk}`
        show_toast(message, 'success', '10000')
    } else if (data.event === 'file-delete') {
        let message = `File Deleted: ${data.pk}`
        show_toast(message, 'success', '10000')
    } else if (data.event === 'message') {
        console.log(`data.message: ${data.message}`)
        let bsclass =
            typeof data.bsclass === 'undefined' ? 'info' : data.bsclass
        console.log(`bsclass: ${bsclass}`)
        let delay = typeof data.delay === 'undefined' ? '10000' : data.delay
        console.log(`delay: ${delay}`)
        show_toast(data.message, data.bsclass, delay)
    }
})

// Init the logout form click function
$('.log-out').on('click', function (event) {
    event.preventDefault()
    $('#log-out').trigger('submit')
})

// Init the flush-cache click function
$('#flush-cache').on('click', function (event) {
    console.log('#flush-cache click')
    event.preventDefault()
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
            show_toast(message, 'danger', '10000')
        },
    })
})
