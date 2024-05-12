socket?.addEventListener('message', function (event) {
    // console.log('socket.message: files.js:', event)
    let data = JSON.parse(event.data)
    console.log(event)
    if (data.event === 'file-new') {
        $.get(`/api/file/${data.pk}`, function (response) {
            console.log(response)
            addDTRow(response)
        })
    }
})
