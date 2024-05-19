// JS included everywhere

let filesDataTable

document.addEventListener('DOMContentLoaded', domContentLoaded)
document
    .querySelectorAll('[data-bs-toggle="popover"]')
    .forEach((el) => new bootstrap.Popover(el))
document
    .querySelectorAll('[data-bs-toggle="tooltip"]')
    .forEach((el) => new bootstrap.Tooltip(el))

const backToTop = document.getElementById('back-to-top')
if (backToTop) {
    window.addEventListener('scroll', debounce(onScroll))
    backToTop.addEventListener('click', () => {
        document.body.scrollTop = 0
        document.documentElement.scrollTop = 0
    })
}

if (typeof ClipboardJS !== 'undefined') {
    new ClipboardJS('.clip')
    $('.clip').on('click', function () {
        const el = $(this)
        el.popover({
            content: 'Copied',
            placement: 'bottom',
            trigger: 'manual',
        })
        el.popover('show')
        setTimeout(function () {
            el.popover('hide')
        }, 2000)
        $(document).on('click', function (e) {
            if (!el.is(e.target) && el.has(e.target).length === 0) {
                el.popover('hide')
            }
        })
    })
}

$('.form-control').on('focus change input', function () {
    $(this).removeClass('is-invalid')
})

/**
 * Initialize Document
 * @function domContentLoaded
 */
function domContentLoaded() {
    // Show any toast generated by template on load
    $('.toast-alert').each(function () {
        let toastAlert = new bootstrap.Toast($(this))
        toastAlert.show()
    })
}

/**
 * On Scroll Callback
 * @function onScroll
 */
function onScroll() {
    if (
        document.body.scrollTop > 20 ||
        document.documentElement.scrollTop > 20
    ) {
        backToTop.style.display = 'block'
    } else {
        backToTop.style.display = 'none'
    }
}

/**
 * Show Bootstrap Toast
 * @function showToast
 * @param {String} message
 * @param {String} bsClass
 * @param {String} delay
 */
function show_toast(message, bsClass = 'success', delay = '6000') {
    let element = $('#toast').clone()
    element.removeAttr('id').addClass(`text-bg-${bsClass}`)
    element.find('.toast-body').text(message)
    element.toast({ delay: parseInt(delay) })
    element.appendTo('.toast-container').toast('show')
}

/**
 * Save Options
 * @function saveOptions
 * @param {InputEvent} event
 */
function saveOptions(event) {
    console.debug(`saveOptions: ${event.type}`, event)
    const form = $(settingsForm)
    // console.debug('form', form)
    const data = new FormData(settingsForm[0])
    // console.debug('data', data)
    $.ajax({
        type: 'post',
        url: window.location.pathname,
        data: data,
        headers: { 'X-CSRFToken': csrftoken },
        success: success,
        error: error,
        cache: false,
        contentType: false,
        processData: false,
    })
    function error(jqXHR) {
        formErrorHandler.call(this, form, jqXHR)
    }
    function success(data) {
        console.debug('success:', data, event)
        if (data.reload) {
            location.reload()
        } else {
            // let message = 'Settings Saved Successfully.'
            // show_toast(message, 'success')
            event.target.classList.add('is-valid')
            setTimeout(() => event.target.classList.remove('is-valid'), 3000)
        }
    }
}

/**
 * Error Message responseJSON.error or jqXHR.statusText
 * @param {jQuery.jqXHR} jqXHR
 */
function messageErrorHandler(jqXHR) {
    if (jqXHR.responseJSON?.error) {
        const message = `${jqXHR.status}: ${jqXHR.responseJSON.error}`
        show_toast(message, 'danger')
    } else {
        const message = `${jqXHR.status}: ${jqXHR.statusText}`
        show_toast(message, 'danger')
    }
}

/**
 * Loop through form errors and display them
 * formErrorHandler.call(this, form, jqXHR)
 * @param {jQuery} form
 * @param {jQuery.jqXHR} jqXHR
 */
function formErrorHandler(form, jqXHR) {
    if (jqXHR.status === 400) {
        let data = jqXHR.responseJSON
        console.log('jqXHR.responseJSON data:', data)
        $(form.prop('elements')).each(function () {
            if (Object.hasOwn(data, this.name)) {
                $(`#${this.name}-invalid`).empty().append(data[this.name])
                $(this).addClass('is-invalid')
            }
        })
    }
    const message = `${jqXHR.status}: ${jqXHR.statusText}`
    show_toast(message, 'danger')
}

/**
 * Debounce Function
 * @function debounce
 * @param {Function} fn
 * @param {Number} timeout
 */
function debounce(fn, timeout = 250) {
    let timeoutID
    return (...args) => {
        clearTimeout(timeoutID)
        timeoutID = setTimeout(() => fn(...args), timeout)
    }
}

/**
 * Throttle Function
 * @function throttle
 * @param {Function} fn
 * @param {Number} limit
 */
function throttle(fn, limit = 250) {
    let lastExecutedTime = 0
    return function (...args) {
        const currentTime = Date.now()
        if (currentTime - lastExecutedTime >= limit) {
            fn(...args)
            lastExecutedTime = currentTime
        }
    }
}
