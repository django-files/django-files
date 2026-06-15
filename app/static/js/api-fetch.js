async function fetchPaginated(path, page, count, extraParams = {}) {
    if (!page) {
        console.warn('no page', page)
        return {}
    }
    const url = new URL(`${globalThis.location.origin}${path}${page}/${count}/`)
    const user = new URL(location.href).searchParams.get('user')
    if (user) url.searchParams.append('user', user)
    for (const [k, v] of Object.entries(extraParams)) {
        if (v) url.searchParams.append(k, v)
    }
    return (await fetch(url)).json()
}

/**
 * Fetch Files Paginated
 * @function fetchFiles
 * @param {Number} page Page Number to Fetch
 * @param {Number} [count] Optional - Number of Files to Fetch
 * @param {String} [album] Optional - See Ralph
 * @return {Promise<Object>} JSON Response Object
 */
export async function fetchFiles(
    page,
    count = 25,
    album = null,
    ordering = null,
    types = null,
    extraParams = {}
) {
    return fetchPaginated('/api/files/', page, count, {
        album,
        ordering,
        type: types,
        ...extraParams,
    })
}

export async function fetchAlbums(page, count = 100) {
    return fetchPaginated('/api/albums/', page, count)
}

export async function fetchAlbumsSearch(query = '', count = 12) {
    const url = new URL(`${globalThis.location.origin}/api/albums/1/${count}/`)
    if (query) url.searchParams.append('search', query)
    return (await fetch(url)).json()
}

export async function fetchShorts(page, count = 100) {
    return fetchPaginated('/api/shorts/', page, count)
}

export async function fetchUsers(page, count = 50) {
    return fetchPaginated('/api/users/', page, count)
}

export async function fetchFile(id) {
    let url = `${globalThis.location.origin}/api/file/${id}`
    const response = await fetch(url)
    return await response.json()
}
