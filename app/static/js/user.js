// JS for Authenticated Users

const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value

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

document.getElementById('show-qrcode').addEventListener('click', showQrCode)

async function showQrCode(event) {
    event.preventDefault()
    console.log('event:', event)
}
