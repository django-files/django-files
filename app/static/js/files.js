$(document).ready(function () {
    // Get and set the csrf_token
    // const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value


    $('#user').change(function () {
        let user = $(this).val()
        console.log('user: ' + user)
        if (user) {
            let url = new URL(location.href)
            url.searchParams.set('user', user)
            location.href = url.toString()
        }
    })
})
