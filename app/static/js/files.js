$(document).ready(function () {
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
