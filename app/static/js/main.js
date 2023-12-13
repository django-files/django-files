// JS included everywhere

$(window).on('load', function () {
    // Show custom toast-alert classes on load
    $('.toast-alert').each(function () {
        let toastAlert = new bootstrap.Toast($(this))
        toastAlert.show()
    })
})

// Init all popover elements

const popoverTriggerList = document.querySelectorAll(
    '[data-bs-toggle="popover"]'
)
const popoverList = [...popoverTriggerList].map(
    (popoverTriggerEl) => new bootstrap.Popover(popoverTriggerEl)
)

// Form Control

$('.form-control').on('change', function () {
    $(this).removeClass('is-invalid')
})

// Back to Top Button

const backToTop = document.getElementById('back-to-top')

backToTop?.addEventListener('click', () => {
    document.body.scrollTop = 0
    document.documentElement.scrollTop = 0
})

if (backToTop) {
    window.onscroll = () => {
        if (
            document.body.scrollTop > 20 ||
            document.documentElement.scrollTop > 20
        ) {
            backToTop.style.display = 'block'
        } else {
            backToTop.style.display = 'none'
        }
    }
}

// ClipboardJS

new ClipboardJS('.clip')

$('.clip').on('click', function () {
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

/**
 * Show Toast with message and optional bsClass and delay
 * TODO: Re-write this function
 * @param {String} message
 * @param {String} bsClass
 * @param {String} delay
 */
function show_toast(message, bsClass = 'info', delay = '5000') {
    let toastContainer = $('.toast-container')
    let toastEl = $(
        '<div class="toast align-items-center border-0" role="alert" aria-live="assertive" aria-atomic="true" data-bs-delay="' +
            delay +
            '"><div class="d-flex"><div class="toast-body"></div><button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button></div></div>'
    )
    toastEl.find('.toast-body').text(message)
    toastEl.addClass('text-bg-' + bsClass)
    toastContainer.append(toastEl)
    let toast = new bootstrap.Toast(toastEl)
    toast.show()
}
