// JS for Authenticated Users

const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value

socket?.addEventListener('message', function (event) {
    console.log('socket.message: user.js:', event)
    let data = JSON.parse(event.data)
    // console.log('data:', data)
    if (data.event === 'file-new') {
        const message = `New File Upload: ${data.pk}`
        show_toast(message, 'success')
    } else if (data.event === 'file-delete') {
        const message = `File Deleted: ${data.pk}`
        show_toast(message, 'success')
    } else if (data.event === 'message') {
        console.log(`data.message: ${data.message}`)
        const bsClass = data.bsClass || 'info'
        const delay = data.delay || '6000'
        show_toast(data.message, bsClass, delay)
    }
})

$('.log-out').on('click', function (event) {
    // console.log('.log-out click', event)
    event.preventDefault()
    $('#log-out').trigger('submit')
})

$('#flush-cache').on('click', function (event) {
    // console.log('#flush-cache click', event)
    event.preventDefault()
    $.ajax({
        type: 'POST',
        url: '/flush-cache/',
        headers: { 'X-CSRFToken': csrftoken },
        success: function (data) {
            console.log('data:', data)
            alert('Cache Flush Successfully Sent...')
            location.reload()
        },
        error: messageErrorHandler,
        cache: false,
        contentType: false,
        processData: false,
    })
})
