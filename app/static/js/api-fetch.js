/**
 * Fetch Files Paginated
 * @function fetchFiles
 * @param {Number} page Page Number to Fetch
 * @param {Number} count Number of Files to Fetch
 * @return {Object} JSON Response Object
 */
export async function fetchFiles(page, count = 25, album = null) {
    let page_url = new URL(location.href)
    if (!page) {
        return console.warn('no page', page)
    }
    let url = `${window.location.origin}/api/files/${page}/${count}/`
    let user = page_url.searchParams.get('user')
    if (album) {
        url = url + `?album=${album}`
    } else if (user) {
        url = url + `?user=${user}`
    }
    const response = await fetch(url)
    const json = await response.json()
    return json
}
