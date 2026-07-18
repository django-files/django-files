// JS for screenshots.html

console.log(`%c LOADING: slideshow.js`, 'color: Lime')

const swiperImages = document.getElementById('swiper-images')
const swiperThumbs = document.getElementById('swiper-thumbs')

// const screenShots = [
//     'https://intranet.cssnr.com/raw/2058202_1730328120.jpg',
//     'https://intranet.cssnr.com/raw/266-1600x1600.jpg',
//     'https://intranet.cssnr.com/raw/820-800x600.jpg',
//     'https://intranet.cssnr.com/raw/p256_1Qv8MEr.png',
//     'https://intranet.cssnr.com/raw/5dhtsegment5dhtsegment5dhtsegment5dhtsegment_Db6ece2.jpg',
//     'https://intranet.cssnr.com/raw/qr-download.png',
// ]

// for (const shot of screenShots) {
//     console.debug('shot', shot)
//     const div = document.createElement('div')
//     div.classList.add('swiper-slide')
//     const img = document.createElement('img')
//     img.src = shot
//     img.alt = shot
//     div.appendChild(img)
//     swiperImages.appendChild(div)
//     swiperThumbs.appendChild(div.cloneNode(true))
// }

// const thumbs = new Swiper('.thumbs', {
//     freeMode: true,
//     grabCursor: true,
//     loop: true,
//     mousewheel: true,
//     slidesPerView: 5,
//     spaceBetween: 8,
//     watchSlidesProgress: true,
// })
//
// const swiper = new Swiper('.images', {
//     grabCursor: true,
//     effect: 'fade',
//     loop: true,
//     mousewheel: true,
//     spaceBetween: 10,
//     zoom: true,
//     keyboard: {
//         enabled: true,
//     },
//     navigation: {
//         nextEl: '.swiper-button-next',
//         prevEl: '.swiper-button-prev',
//     },
//     pagination: {
//         el: '.swiper-pagination',
//         type: 'fraction',
//     },
//     thumbs: {
//         swiper: thumbs,
//     },
// })

document.addEventListener('DOMContentLoaded', () => {
    console.log(`%c DOMContentLoaded: slideshow.js`, 'color: Lime')
    // console.log('albumsDataTable:', albumsDataTable)
})

let bufferedFiles = []
let swiperInitialized = false
let thumbsSwiper = null
let imagesSwiper = null

/**
 * Reset the slideshow buffer and destroy active swiper instances.
 * Call when the underlying dataset changes (e.g. user filter).
 */
// eslint-disable-next-line no-unused-vars
function resetSlideshow() {
    bufferedFiles = []
    if (thumbsSwiper) {
        thumbsSwiper.destroy(true, true)
        thumbsSwiper = null
    }
    if (imagesSwiper) {
        imagesSwiper.destroy(true, true)
        imagesSwiper = null
    }
    swiperInitialized = false
    swiperImages.replaceChildren()
    swiperThumbs.replaceChildren()
}

/**
 * Buffer file data for the slideshow.
 * Full-size images are NOT loaded until the slideshow offcanvas is opened.
 * If the slideshow is already open, new slides are appended immediately.
 */
// eslint-disable-next-line no-unused-vars
function slideshowCallback(data) {
    console.log(`%c slideshowCallback: data:`, 'color: Yellow', data)
    const mediaFiles = data.files.filter(
        (f) => f.mime?.startsWith('image/') || f.mime?.startsWith('video/')
    )
    for (const file of mediaFiles) {
        console.debug(`%c file:`, 'color: Lime', file)
    }
    bufferedFiles.push(...mediaFiles)
    if (swiperInitialized) {
        appendSlidesToSwiper(mediaFiles)
    }
}

// Swiper's native `loading="lazy"` deferral relies on each slide's real
// on-screen position, but the main swiper uses the `fade` effect, which
// stacks every slide at the same on-screen box (crossfade via opacity), so
// the browser can't tell "off-screen" slides apart by viewport distance.
// Instead, images are built with a `data-src` placeholder and the real
// `src` is only assigned for the active slide (+/- one) via
// hydrateVisibleSlides(), driven by Swiper's slide-active/prev/next
// classes on init/slideChange — which stay correct through loop mode too.
function buildLazyImage(src, alt) {
    const img = document.createElement('img')
    img.dataset.src = src
    img.alt = alt
    return img
}

function buildLazyPreloader(img) {
    const preloader = document.createElement('div')
    preloader.className = 'swiper-lazy-preloader'
    img.addEventListener('load', () => preloader.remove(), { once: true })
    return preloader
}

function hydrateVisibleSlides(swiperEl) {
    if (!swiperEl) return
    swiperEl
        .querySelectorAll(
            '.swiper-slide-active img[data-src], .swiper-slide-prev img[data-src], .swiper-slide-next img[data-src]'
        )
        .forEach((img) => {
            if (!img.src) img.src = img.dataset.src
        })
}

function buildSlide(file) {
    const div = document.createElement('div')
    div.classList.add('swiper-slide')
    if (file.mime?.startsWith('video/')) {
        const poster = document.createElement('div')
        poster.className = 'slideshow-video-poster'
        if (file.thumb) {
            const img = buildLazyImage(file.thumb, file.name)
            poster.appendChild(img)
            poster.appendChild(buildLazyPreloader(img))
        }
        const playBtn = document.createElement('button')
        playBtn.className =
            'slideshow-play-btn d-flex align-items-center justify-content-center rounded-circle'
        playBtn.setAttribute('aria-label', 'Play video')
        playBtn.innerHTML = '<i class="fa-solid fa-play"></i>'
        poster.appendChild(playBtn)
        poster.addEventListener('click', () => {
            const video = document.createElement('video')
            video.src = file.raw
            video.controls = true
            video.autoplay = true
            div.innerHTML = ''
            div.appendChild(video)
        })
        div.appendChild(poster)
    } else {
        const url = new URL(file.raw)
        url.searchParams.set('view', 'gallery')
        const img = buildLazyImage(url.toString(), file.name)
        div.appendChild(img)
        div.appendChild(buildLazyPreloader(img))
    }
    return div
}

function buildThumbSlide(file) {
    const div = document.createElement('div')
    div.classList.add('swiper-slide')
    if (file.mime?.startsWith('video/') && file.thumb) {
        // Use the server-generated thumbnail image for the strip
        div.appendChild(buildLazyImage(file.thumb, file.name))
    } else if (file.mime?.startsWith('video/')) {
        // No thumbnail yet — show a film icon placeholder
        const icon = document.createElement('div')
        icon.className = 'slideshow-video-thumb'
        icon.innerHTML = '<i class="fa-solid fa-film"></i>'
        div.appendChild(icon)
    } else {
        // Use the server-generated thumbnail for the strip; fall back to
        // the full-size image only if no thumb is available.
        let src = file.thumb
        if (!src) {
            const url = new URL(file.raw)
            url.searchParams.set('view', 'gallery')
            src = url.toString()
        }
        div.appendChild(buildLazyImage(src, file.name))
    }
    return div
}

function appendSlidesToSwiper(files) {
    for (const file of files) {
        swiperImages.appendChild(buildSlide(file))
        swiperThumbs.appendChild(buildThumbSlide(file))
    }
    if (thumbsSwiper) thumbsSwiper.update()
    if (imagesSwiper) imagesSwiper.update()
    hydrateVisibleSlides(swiperImages)
    hydrateVisibleSlides(swiperThumbs)
}

function initSlideshow() {
    if (swiperInitialized) return
    swiperInitialized = true
    console.log(
        `%c initSlideshow: building ${bufferedFiles.length} slides`,
        'color: Lime'
    )

    appendSlidesToSwiper(bufferedFiles)

    thumbsSwiper = new Swiper('.thumbs', {
        freeMode: true,
        grabCursor: true,
        loop: true,
        mousewheel: true,
        slidesPerView: 5,
        spaceBetween: 8,
        watchSlidesProgress: true,
        on: {
            init: () => hydrateVisibleSlides(swiperThumbs),
            slideChange: () => hydrateVisibleSlides(swiperThumbs),
            slideChangeTransitionEnd: () => hydrateVisibleSlides(swiperThumbs),
        },
    })

    imagesSwiper = new Swiper('.images', {
        grabCursor: true,
        effect: 'fade',
        loop: true,
        mousewheel: true,
        spaceBetween: 10,
        zoom: true,
        keyboard: {
            enabled: true,
        },
        navigation: {
            nextEl: '.swiper-button-next',
            prevEl: '.swiper-button-prev',
        },
        pagination: {
            el: '.swiper-pagination',
            type: 'fraction',
        },
        thumbs: {
            swiper: thumbsSwiper,
        },
        on: {
            init: () => hydrateVisibleSlides(swiperImages),
            slideChange() {
                hydrateVisibleSlides(swiperImages)
                swiperImages.querySelectorAll('video').forEach((v) => {
                    v.pause()
                })
            },
            slideChangeTransitionEnd: () => hydrateVisibleSlides(swiperImages),
        },
    })
}

const myOffcanvas = document.getElementById('offcanvas-bottom')
myOffcanvas.addEventListener('show.bs.offcanvas', initSlideshow)
myOffcanvas.addEventListener('hide.bs.offcanvas', () => {
    if (document.fullscreenElement) {
        console.log(`Close Button: %c EXIT`, 'color: Yellow')
        document.exitFullscreen()
    }
})

document.getElementById('toggle-show').addEventListener('click', (e) => {
    e.preventDefault()
    if (document.fullscreenElement) {
        console.log(`Full Screen Button: %c EXIT`, 'color: Yellow')
        document.exitFullscreen()
    } else {
        console.log(`Full Screen Button: %c ENTER`, 'color: Lime')
        myOffcanvas.requestFullscreen()
    }
})

const thumbsEl = document.querySelector('.thumbs')
const imagesEl = document.querySelector('.images')
document.getElementById('toggle-thumbs').addEventListener('click', (e) => {
    e.preventDefault()
    if (thumbsEl.classList.contains('d-none')) {
        thumbsEl.classList.remove('d-none')
        imagesEl.style.height = '80%'
    } else {
        thumbsEl.classList.add('d-none')
        imagesEl.style.height = '100%'
    }
})
