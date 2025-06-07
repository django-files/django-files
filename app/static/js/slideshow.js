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

document.addEventListener('DOMContentLoaded', (event) => {
    console.log(`%c DOMContentLoaded: slideshow.js`, 'color: Lime')
    // console.log('albumsDataTable:', albumsDataTable)
})

function slideshowCallback(data) {
    console.log(`%c slideshowCallback: data:`, 'color: Yellow', data)
    for (const file of data.files) {
        console.log(`%c file:`, 'color: Lime', file)
        const div = document.createElement('div')
        div.classList.add('swiper-slide')
        const img = document.createElement('img')

        const url = new URL(file.raw)
        url.searchParams.set('view', 'gallery')

        img.src = url.toString()
        img.alt = file.name
        div.appendChild(img)
        swiperImages.appendChild(div)
        swiperThumbs.appendChild(div.cloneNode(true))
    }

    const thumbs = new Swiper('.thumbs', {
        freeMode: true,
        grabCursor: true,
        loop: true,
        mousewheel: true,
        slidesPerView: 5,
        spaceBetween: 8,
        watchSlidesProgress: true,
    })

    const swiper = new Swiper('.images', {
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
            swiper: thumbs,
        },
    })
}

const myOffcanvas = document.getElementById('offcanvasBottom')
myOffcanvas.addEventListener('hide.bs.offcanvas', () => {
    if (document.fullscreenElement) {
        console.log(`Close Button: %c EXIT`, 'color: Yellow')
        document.exitFullscreen()
    }
})

const fullScreen = document.getElementById('slideshow-fullscreen')
fullScreen.addEventListener('click', (event) => {
    event.preventDefault()
    if (document.fullscreenElement) {
        console.log(`Full Screen Button: %c EXIT`, 'color: Yellow')
        document.exitFullscreen()
    } else {
        console.log(`Full Screen Button: %c ENTER`, 'color: Lime')
        myOffcanvas.requestFullscreen()
    }
})
