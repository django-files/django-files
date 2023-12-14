// JS for Authenticated Users

const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value

socket?.addEventListener('message', function (event) {
    console.log('socket.message: user.js:', event)
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

$('.log-out').on('click', function (event) {
    // console.log('.log-out click', event)
    event.preventDefault()
    $('#log-out').trigger('submit')
})

$('#flush-cache').on('click', function (event) {
    // console.log('#flush-cache click', event)
    event.preventDefault()
    $.ajax({
        url: '/flush-cache/',
        type: 'POST',
        headers: { 'X-CSRFToken': csrftoken },
        success: function () {
            alert('Cache Flush Successfully Sent...')
            location.reload()
        },
        error: function (jqXHR) {
            const message = `${jqXHR.status}: ${jqXHR.statusText}`
            show_toast(message, 'danger', '6000')
        },
    })
})
