// Document Dot Ready
$(document).ready(function () {
    // Local login form handler
    $('.form-control').focus(function () {
        $(this).removeClass('is-invalid')
    })
    $('#login-form').on('submit', function (event) {
        event.preventDefault()
        if ($('#login-button').hasClass('disabled')) {
            return
        }
        let formData = new FormData($(this)[0])
        $.ajax({
            url: $('#login-form').attr('action'),
            type: 'POST',
            data: formData,
            beforeSend: function () {
                $('#login-button').addClass('disabled')
            },
            complete: function () {
                $('#login-button').removeClass('disabled')
            },
            success: function () {
                location.reload()
            },
            error: function () {
                $('#login-form input').addClass('is-invalid')
            },
            cache: false,
            contentType: false,
            processData: false,
        })
    })

    // var vid = document.getElementById("bgvid");
    // var pauseButton = document.querySelector("#pause");
    //
    // if (window.matchMedia('(prefers-reduced-motion)').matches) {
    //     vid.removeAttribute("autoplay");
    //     vid.pause();
    //     pauseButton.innerHTML = "Play";
    // }
    //
    // pauseButton.addEventListener("click", function() {
    //     vid.classList.toggle("stopfade");
    //     console.log('one');
    //     if (vid.paused) {
    //         vid.play();
    //         pauseButton.innerHTML = "Pause";
    //     } else {
    //         vid.pause();
    //         pauseButton.innerHTML = "Play";
    //     }
    // })
})
