$(document).ready(function () {
    // Back to Top Button, Function, and Listener
    let mybutton = document.getElementById('btn-back-to-top')
    if (mybutton) {
        window.onscroll = function () {
            scrollFunction()
        }
        function scrollFunction() {
            if (
                document.body.scrollTop > 20 ||
                document.documentElement.scrollTop > 20
            ) {
                mybutton.style.display = 'block'
            } else {
                mybutton.style.display = 'none'
            }
        }
        mybutton.addEventListener('click', backToTop)
        function backToTop() {
            document.body.scrollTop = 0
            document.documentElement.scrollTop = 0
        }
    }

    // // Monitor home websockets for new data
    // const socket = new WebSocket('wss://' + window.location.host + '/ws/home/');
    // console.log('Websockets Connected.');
    // socket.onmessage = function(event) {
    //     let data = JSON.parse(event.data);
    //     console.log(data);
    // };

    // Init a ClipboardJS attribute
    new ClipboardJS('.clip')

    // Onclick listener for clip
    $(document).ready(function () {
        $('.clip').click(function () {
            var clipElement = $(this)
            clipElement.popover({
                content: 'Copied',
                placement: 'bottom',
                trigger: 'manual',
            })
            clipElement.popover('show')
            setTimeout(function () {
                clipElement.popover('hide')
            }, 2000)
            $(document).on('click', function (e) {
                if (
                    !clipElement.is(e.target) &&
                    clipElement.has(e.target).length === 0
                ) {
                    clipElement.popover('hide')
                }
            })
        })
    })

    // Show custom toast-alert classes on load
    $('.toast-alert').each(function () {
        console.log($(this).html())
        let toastAlert = new bootstrap.Toast($(this))
        toastAlert.show()
    })
})

// Generate a BS toast and show it
function show_toast(message, bsClass = 'info', delay = '5000') {
    let toastContainer = $('.toast-container')
    let toast = $(
        '<div class="toast align-items-center border-0" role="alert" aria-live="assertive" aria-atomic="true" data-bs-delay="' +
            delay +
            '"><div class="d-flex"><div class="toast-body"></div><button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button></div></div>'
    )
    toast.find('.toast-body').text(message)
    toast.addClass('text-bg-' + bsClass)
    toastContainer.append(toast)
    let jsToast = new bootstrap.Toast(toast)
    jsToast.show()
}
