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
 * Buffer file data for the slideshow.
 * Full-size images are NOT loaded until the slideshow offcanvas is opened.
 * If the slideshow is already open, new slides are appended immediately.
 */
// eslint-disable-next-line no-unused-vars
function slideshowCallback(data) {
    console.log(`%c slideshowCallback: data:`, 'color: Yellow', data)
    for (const file of data.files) {
        console.debug(`%c file:`, 'color: Lime', file)
    }
    bufferedFiles.push(...data.files)
    if (swiperInitialized) {
        appendSlidesToSwiper(data.files)
    }
}

function buildSlide(file) {
    const div = document.createElement('div')
    div.classList.add('swiper-slide')
    if (file.mime?.startsWith('video/')) {
        const poster = document.createElement('div')
        poster.className = 'slideshow-video-poster'
        if (file.thumb) {
            const img = document.createElement('img')
            img.src = file.thumb
            img.alt = file.name
            poster.appendChild(img)
        }
        const playBtn = document.createElement('button')
        playBtn.className = 'slideshow-play-btn'
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
        const img = document.createElement('img')
        const url = new URL(file.raw)
        url.searchParams.set('view', 'gallery')
        img.src = url.toString()
        img.alt = file.name
        div.appendChild(img)
    }
    return div
}

function buildThumbSlide(file) {
    const div = document.createElement('div')
    div.classList.add('swiper-slide')
    if (file.mime?.startsWith('video/') && file.thumb) {
        // Use the server-generated thumbnail image for the strip
        const img = document.createElement('img')
        img.src = file.thumb
        img.alt = file.name
        div.appendChild(img)
    } else if (file.mime?.startsWith('video/')) {
        // No thumbnail yet — show a film icon placeholder
        const icon = document.createElement('div')
        icon.className = 'slideshow-video-thumb'
        icon.innerHTML = '<i class="fa-solid fa-film"></i>'
        div.appendChild(icon)
    } else {
        const img = document.createElement('img')
        const url = new URL(file.raw)
        url.searchParams.set('view', 'gallery')
        img.src = url.toString()
        img.alt = file.name
        div.appendChild(img)
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
            slideChange() {
                swiperImages.querySelectorAll('video').forEach((v) => {
                    v.pause()
                })
            },
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
