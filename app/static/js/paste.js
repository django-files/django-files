$(document).ready(function () {
    // Get and set the csrf_token
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value

    // Handle paste submissions
    $('#sendPaste').submit(function (event) {
        event.preventDefault()
        // let data = $('#paste-data').val()
        let formData = new FormData($(this)[0])
        formData.forEach((value, key) => (formData[key] = value))
        formData['method'] = 'paste-text'
        let data = JSON.stringify(formData)
        console.log(`data: ${data}`)
        socket.send(data)
    })
})
