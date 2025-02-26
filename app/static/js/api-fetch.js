/**
 * Fetch Files Paginated
 * @function fetchFiles
 * @param {Number} page Page Number to Fetch
 * @param {Number} [count] Optional - Number of Files to Fetch
 * @param {String} [album] Optional - See Ralph
 * @return {Object} JSON Response Object
 */
export async function fetchFiles(page, count = 25, album = null) {
    let pageURL = new URL(location.href)
    if (!page) {
        return console.warn('no page', page)
    }
    let url = new URL(`${window.location.origin}/api/files/${page}/${count}/`)
    let user = pageURL.searchParams.get('user')
    if (album) {
        url.searchParams.append('album', album)
    }
    if (user) {
        url.searchParams.append('user', user)
    }
    const response = await fetch(url)
    return await response.json()
}

export async function fetchAlbums(page, count = 100) {
    let pageURL = new URL(location.href)
    if (!page) {
        return console.warn('no page', page)
    }
    let url = new URL(`${window.location.origin}/api/albums/${page}/${count}/`)
    let user = pageURL.searchParams.get('user')
    if (user) {
        url.searchParams.append('user', user)
    }
    const response = await fetch(url)
    return await response.json()
}

export async function fetchFile(id) {
    let url = `${window.location.origin}/api/file/${id}`
    const response = await fetch(url)
    return await response.json()
}
