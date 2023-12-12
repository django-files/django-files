// JS for logged in Users

// Get and set the csrf_token
const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value

// Monitor websockets for new data and update results
socket.addEventListener('message', (event) => {
    console.log('user.js socket.addEventListener message function')
    let data = JSON.parse(event.data)
    console.log(data)
    if (data.event === 'file-new') {
        let message = `New File Upload: ${data.pk}`
        show_toast(message, 'success', '10000')
    } else if (data.event === 'file-delete') {
        let message = `File Deleted: ${data.pk}`
        show_toast(message, 'success', '10000')
        if (filesTable.length) {
            let count = $('#files-table tr').length
            $(`#file-${data.pk}`).remove()
            if (count <= 2) {
                console.log('removing #files-table@ #files-table')
                filesTable.remove()
            }
        }
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
$('#flush-cache').on('click', function () {
    console.log('#flush-cache click function')
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
    return false
})
